import json

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from .config import settings
from .schemas import Action
from .tools import search_doctors, search_hospitals

client = OpenAI(api_key=settings.openai_api_key, base_url="https://backend.sovereigneg.com/v1") if settings.openai_api_key else None

SYSTEM = """
You are a prototype patient decision assistant, not a doctor. Do not diagnose or claim certainty.
Ask focused clarification questions when needed and suggest a high-level next step.
For potentially life-threatening symptoms, recommend emergency evaluation without delaying for provider search.

Provider grounding:
- Never include a doctor's, hospital's, or clinic's proper name or provider-specific facts in your message.
- Discuss provider types generically (for example, a cardiologist or a hospital option).
- If provider options are appropriate, call the matching search tool. The application displays returned
  database records separately; do not repeat provider identities in your message.
- Never invent provider facts. If a search has no results, say no matching option was found in the prototype database.

Return a concise JSON response matching the required structured output with fields `message` and `action`.
Allowed actions: ER, URGENT_CARE, SPECIALIST, SECOND_OPINION, SELF_CARE, CLARIFY.
Respond in the user's language when practical.
"""

TOOLS = [
    {"type": "function", "function": {"name": "search_doctors", "description": "Search the prototype database for available doctors. Use when a specialist is appropriate.", "strict": True,
     "parameters": {"type": "object", "properties": {"specialty": {"type": ["string", "null"]}, "city": {"type": ["string", "null"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 5}}, "required": ["specialty", "city", "limit"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "search_hospitals", "description": "Search the prototype database for hospitals. Use when hospital options are appropriate.", "strict": True,
     "parameters": {"type": "object", "properties": {"city": {"type": ["string", "null"]}, "emergency_available": {"type": ["boolean", "null"]}, "limit": {"type": "integer", "minimum": 1, "maximum": 5}}, "required": ["city", "emergency_available", "limit"], "additionalProperties": False}}},
]


class DoctorToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    specialty: str | None
    city: str | None
    limit: int = Field(ge=1, le=5)


class HospitalToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    city: str | None
    emergency_available: bool | None
    limit: int = Field(ge=1, le=5)


OUTPUT_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "patient_decision",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "action": {"type": "string", "enum": [action.value for action in Action]},
            },
            "required": ["message", "action"],
            "additionalProperties": False,
        },
    },
}

# Deliberately small prototype guard, not a clinical triage engine.
EMERGENCY_PHRASES = (
    "chest pain", "severe trouble breathing", "difficulty breathing", "can't breathe", "cannot breathe",
    "signs of stroke", "face drooping", "slurred speech", "uncontrolled bleeding", "fainting",
    "ألم شديد في الصدر", "ألم في الصدر", "صعوبة شديدة في التنفس", "لا أستطيع التنفس", "نزيف لا يتوقف", "إغماء",
)


def emergency_guard(message: str) -> bool:
    text = message.casefold()
    # Avoid routing explicitly negated, present-tense examples such as "no chest pain now".
    negations = ("no", "not", "without", "don't have", "do not have", "not having", "not experiencing",
                 "لا يوجد", "ليس لدي", "لا أعاني من", "لا أشعر ب")
    for phrase in EMERGENCY_PHRASES:
        start = 0
        while (index := text.find(phrase, start)) >= 0:
            prefix = text[max(0, index - 35):index].rstrip()
            if not any(prefix.endswith(negation) for negation in negations):
                return True
            start = index + len(phrase)
    return False


def fallback(message: str):
    if emergency_guard(message):
        return _emergency_response(message)
    return {"message": "I can help with a general next step, but this prototype needs an AI API key for the full agent flow.", "action": Action.CLARIFY, "recommendations": [], "tool_calls": []}


def _emergency_response(message: str):
    if any("\u0600" <= char <= "\u06ff" for char in message):
        text = "قد تتطلب هذه الأعراض عناية فورية. يرجى التوجه إلى الطوارئ الآن. هذا النموذج الأولي لا يستطيع تقييم الحالات الطارئة."
    else:
        text = "Your symptoms may need immediate attention. Please seek emergency medical evaluation now. This prototype cannot assess emergencies."
    return {"message": text, "action": Action.ER, "recommendations": [], "tool_calls": []}


def _parse_output(message) -> tuple[str, Action]:
    try:
        result = json.loads(message.content)
        return result["message"], Action(result["action"])
    except (ValueError, KeyError, TypeError):
        return "I could not determine a safe next step. Could you share a little more information?", Action.CLARIFY


def run_agent(db: Session, message: str, history: list[dict]):
    if emergency_guard(message):
        return _emergency_response(message)
    if not client:
        return fallback(message)

    messages = [{"role": "system", "content": SYSTEM}]
    messages.extend(item.model_dump() if hasattr(item, "model_dump") else item for item in history[-20:])
    messages.append({"role": "user", "content": message})
    tool_calls = []
    verified_records = []
    response = client.chat.completions.create(model=settings.openai_model, messages=messages, tools=TOOLS,
                                              response_format=OUTPUT_FORMAT, max_tokens=500)

    for _ in range(3):
        assistant_message = response.choices[0].message
        calls = assistant_message.tool_calls or []
        if not calls:
            break
        messages.append(assistant_message.model_dump(exclude_none=True))
        for call in calls:
            try:
                raw_args = json.loads(call.function.arguments)
                if call.function.name == "search_doctors":
                    args = DoctorToolArgs.model_validate(raw_args)
                    result = search_doctors(db, **args.model_dump())
                elif call.function.name == "search_hospitals":
                    args = HospitalToolArgs.model_validate(raw_args)
                    result = search_hospitals(db, **args.model_dump())
                else:
                    result = {"error": "Unknown tool"}
                if isinstance(result, list):
                    verified_records.extend(result)
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
                result = {"error": "Invalid tool arguments", "details": str(exc)}
            except Exception:
                result = {"error": "Database search failed; do not claim that no providers were found."}
            tool_calls.append(call.function.name)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
        response = client.chat.completions.create(model=settings.openai_model, messages=messages, tools=TOOLS,
                                                  response_format=OUTPUT_FORMAT, max_tokens=500)

    text, action = _parse_output(response.choices[0].message)
    recommendations = []
    seen = set()
    for row in verified_records:
        if "name_en" in row and "specialty" in row:
            key = ("doctor", row["id"])
            recommendation = {"type": "doctor", "id": row["id"], "name": row["name_en"], "specialty": row["specialty"], "hospital": row["hospital"], "city": row["city"]}
        elif "name_en" in row and "emergency_available" in row:
            key = ("hospital", row["id"])
            recommendation = {"type": "hospital", "id": row["id"], "name": row["name_en"], "specialty": None, "hospital": row["name_en"], "city": row["city"]}
        else:
            continue
        if key not in seen:
            seen.add(key)
            recommendations.append(recommendation)
    return {"message": text, "action": action, "recommendations": recommendations, "tool_calls": tool_calls}
