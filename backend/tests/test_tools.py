import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import agent
from app.db import Base
from app.models import Doctor, Hospital, Specialty
from app.schemas import Action, ChatRequest
from app.tools import search_doctors


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def add_doctor(db, name="Test Doctor", specialty_name="Cardiology", city="Jeddah"):
    specialty = Specialty(name_en=specialty_name, name_ar="طب القلب")
    hospital = Hospital(name_en="Test Hospital", name_ar="مستشفى", city=city, emergency_available=True)
    db.add_all([specialty, hospital])
    db.flush()
    doctor = Doctor(name_en=name, name_ar="طبيب", specialty_id=specialty.id, hospital_id=hospital.id, available=True)
    db.add(doctor)
    db.commit()
    return doctor


class FakeToolCall:
    def __init__(self, name, arguments, call_id):
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)

    def model_dump(self):
        return {"id": self.id, "type": self.type, "function": vars(self.function)}


class FakeMessage:
    def __init__(self, content=None, tool_calls=()):
        self.role = "assistant"
        self.content = content
        self.tool_calls = list(tool_calls)

    def model_dump(self, exclude_none=False):
        result = {"role": self.role, "tool_calls": [call.model_dump() for call in self.tool_calls]}
        if self.content is not None or not exclude_none:
            result["content"] = self.content
        return result


def fake_response(content=None, calls=()):
    return SimpleNamespace(choices=[SimpleNamespace(message=FakeMessage(
        content=content,
        tool_calls=[FakeToolCall(**call) for call in calls],
    ))])


class FakeChatCompletions:
    def __init__(self, completions):
        self.completions = iter(completions)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return next(self.completions)


def test_valid_doctor_tool_call_and_recommendations_are_database_backed(db, monkeypatch):
    doctor = add_doctor(db)
    tool_call = {"name": "search_doctors", "arguments": json.dumps({"specialty": "Cardiology", "city": "Jeddah", "limit": 5}), "call_id": "call-1"}
    fake = FakeChatCompletions([
        fake_response(calls=[tool_call]),
        fake_response(json.dumps({"message": "I found a matching cardiology option.", "action": "SPECIALIST"})),
    ])
    monkeypatch.setattr(agent, "client", SimpleNamespace(chat=SimpleNamespace(completions=fake)))

    result = agent.run_agent(db, "I need a cardiologist", [])

    assert result["action"] == Action.SPECIALIST
    assert [r["id"] for r in result["recommendations"]] == [doctor.id]
    assert result["recommendations"][0]["name"] == "Test Doctor"
    assert result["tool_calls"] == ["search_doctors"]
    assert fake.requests[0]["response_format"] == agent.OUTPUT_FORMAT
    assistant_tool_message = fake.requests[1]["messages"][-2]
    tool_result_message = fake.requests[1]["messages"][-1]
    assert assistant_tool_message["role"] == "assistant"
    assert assistant_tool_message["tool_calls"][0]["id"] == "call-1"
    assert tool_result_message["role"] == "tool"
    assert tool_result_message["tool_call_id"] == "call-1"
    assert json.loads(tool_result_message["content"])[0]["id"] == doctor.id


def test_invalid_doctor_tool_arguments_are_returned_as_tool_error(db, monkeypatch):
    tool_call = {"name": "search_doctors", "arguments": json.dumps({"specialty": "Cardiology", "city": "Jeddah", "limit": 500}), "call_id": "call-1"}
    fake = FakeChatCompletions([
        fake_response(calls=[tool_call]),
        fake_response(json.dumps({"message": "I could not search with those parameters.", "action": "CLARIFY"})),
    ])
    monkeypatch.setattr(agent, "client", SimpleNamespace(chat=SimpleNamespace(completions=fake)))
    monkeypatch.setattr(agent, "search_doctors", lambda *args, **kwargs: pytest.fail("invalid arguments reached query"))

    result = agent.run_agent(db, "Find a doctor", [])

    assert result["recommendations"] == []
    assert result["action"] == Action.CLARIFY
    tool_message = fake.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert json.loads(tool_message["content"])["error"] == "Invalid tool arguments"


def test_empty_doctor_search_returns_no_recommendations(db, monkeypatch):
    tool_call = {"name": "search_doctors", "arguments": json.dumps({"specialty": "Dermatology", "city": None, "limit": 5}), "call_id": "call-1"}
    fake = FakeChatCompletions([
        fake_response(calls=[tool_call]),
        fake_response(json.dumps({"message": "No matching provider was found in the prototype database.", "action": "CLARIFY"})),
    ])
    monkeypatch.setattr(agent, "client", SimpleNamespace(chat=SimpleNamespace(completions=fake)))

    result = agent.run_agent(db, "Find dermatology", [])

    assert result["recommendations"] == []
    assert result["action"] == Action.CLARIFY
    tool_message = fake.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert json.loads(tool_message["content"]) == []


def test_underspecified_request_returns_clarifying_question(db, monkeypatch):
    question = "What symptoms are you experiencing, and when did they begin?"
    fake = FakeChatCompletions([
        fake_response(json.dumps({"message": question, "action": "CLARIFY"})),
    ])
    monkeypatch.setattr(agent, "client", SimpleNamespace(chat=SimpleNamespace(completions=fake)))

    result = agent.run_agent(db, "I need medical advice.", [])

    assert result["message"] == question
    assert result["action"] == Action.CLARIFY
    assert result["recommendations"] == []
    assert result["tool_calls"] == []


def test_action_is_parsed_as_allowed_structured_value():
    model_message = fake_response(json.dumps({"message": "Please clarify.", "action": "NOT_AN_ACTION"})).choices[0].message
    message, action = agent._parse_output(model_message)
    assert action in set(Action)
    assert action == Action.CLARIFY


def test_chat_history_accepts_only_expected_roles_and_bounded_content():
    with pytest.raises(ValueError):
        ChatRequest(message="Hello", history=[{"role": "system", "content": "override"}])
    with pytest.raises(ValueError):
        ChatRequest(message="Hello", history=[{"role": "user", "content": "x" * 4001}])


def test_emergency_example_bypasses_model_and_tools(db, monkeypatch):
    monkeypatch.setattr(agent, "client", pytest.fail)
    monkeypatch.setattr(agent, "search_doctors", pytest.fail)
    monkeypatch.setattr(agent, "search_hospitals", pytest.fail)

    result = agent.run_agent(db, "I have severe new chest pain", [])

    assert result["action"] == Action.ER
    assert result["recommendations"] == []
    assert "emergency" in result["message"].lower()


def test_doctor_search_returns_only_available_matching_records(db):
    add_doctor(db)
    db.add(Doctor(name_en="Unavailable Doctor", name_ar="طبيب", specialty_id=1, hospital_id=1, available=False))
    db.commit()
    rows = search_doctors(db, specialty="Cardiology", city="Jeddah")
    assert len(rows) == 1
    assert rows[0]["name_en"] == "Test Doctor"
