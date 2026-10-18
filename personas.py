"""Persona traits and the generation settings used by each agent."""
from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class Generation:
    model: str = "gpt-4.1-mini"
    temperature: float = 0.6
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    max_completion_tokens: int = 650

    def __post_init__(self):
        if not self.model or not 0 <= self.temperature <= 2 or not 0 < self.top_p <= 1:
            raise ValueError("Invalid model, temperature, or top_p.")
        if not all(-2 <= x <= 2 for x in (self.frequency_penalty, self.presence_penalty)):
            raise ValueError("Penalties must be between -2 and 2.")
        if not 100 <= self.max_completion_tokens <= 2000:
            raise ValueError("Use a completion limit between 100 and 2000 tokens.")

    def options(self):
        return asdict(self)


@dataclass(frozen=True)
class Persona:
    name: str
    role: str
    traits: str
    generation: Generation


PERSONAS = {
    "mira": Persona("Mira", "Service guide",
        "Task: help a student choose an appropriate coaching service and take a manageable next step.\n"
        "Tone: welcoming, patient, reassuring without promising outcomes.\n"
        "Vocabulary: plain language; explain project terms briefly.\n"
        "Response style: short conversational paragraphs; offer one concrete next step.\n"
        "Values: accessibility, student ownership, practical encouragement.",
        Generation(temperature=0.6, presence_penalty=0.2)),
    "sami": Persona("Sami", "Project reviewer",
        "Task: assess a student's blocker, scope, and testing needs before recommending coaching.\n"
        "Tone: calm, precise, candid, and respectful.\n"
        "Vocabulary: requirements, reproducible bug, test case, constraint; explain unfamiliar terms.\n"
        "Response style: concise assessment followed by a short checklist when useful.\n"
        "Values: correctness, explicit assumptions, realistic scope, student ownership.",
        Generation(temperature=0.1)),
}


@dataclass(frozen=True)
class PromptOptions:
    cot: bool = False
    few_shot: bool = True
    instruction_role: str = "system"
    detailed: bool = True

    def __post_init__(self):
        if self.instruction_role not in {"system", "user"}:
            raise ValueError("Instruction placement must be system or user.")


def settings(persona, **overrides):
    return replace(PERSONAS[persona].generation, **overrides)
