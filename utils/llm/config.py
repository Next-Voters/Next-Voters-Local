from enum import Enum


class LLMModel(str, Enum):
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"


DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 2000
DEFAULT_TIMEOUT = 30


MINI_LLM_CONFIG = {
    "model": LLMModel.GPT_4O_MINI,
    "temperature": 0.0,
    "max_tokens": 1500,
    "timeout": 30,
}

AGENT_LLM_CONFIG = {
    "model": LLMModel.GPT_4O,
    "temperature": 0.0,
    "max_tokens": 2000,
    "timeout": 30,
}
