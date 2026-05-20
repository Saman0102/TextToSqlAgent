import json
import os
import re
from typing import Any, Dict

# Ensure transformers does not attempt to import torchvision for text-only usage.
os.environ.setdefault('TRANSFORMERS_NO_TORCHVISION_IMPORTS', '1')

from config_loader import get_config_value
from prompts.templates import (
    DECOMPOSE_SYSTEM_PROMPT,
    DECOMPOSE_USER_PROMPT,
    FIX_SYSTEM_PROMPT,
    FIX_USER_PROMPT,
    GENERATE_SYSTEM_PROMPT,
    GENERATE_USER_PROMPT,
    SCHEMA_CONTEXT,
)
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)

DEFAULT_MODEL = get_config_value('GEMINI_MODEL', 'gemini-2.0-flash')
DEFAULT_MAX_TOKENS = int(get_config_value('GEMINI_MAX_TOKENS', 512))
DEFAULT_TIMEOUT = int(get_config_value('GEMINI_TIMEOUT', 60))



def _get_gemini_api_key() -> str:
	api_key = get_config_value('GOOGLE_GEMINI_API_KEY')
	if not api_key:
		raise ValueError('GOOGLE_GEMINI_API_KEY is not set in config/.secrets.yaml')
	return api_key



def _build_prompt(system_prompt: str, user_prompt: str) -> str:
	return f"System: {system_prompt}\nUser: {user_prompt}\nAssistant:"



def _call_llm(system_prompt: str, user_prompt: str, temperature: float = 0) -> str:
	api_key = _get_gemini_api_key()
	prompt = _build_prompt(system_prompt, user_prompt)
	# Try Gemini API first
	try:
		genai.configure(api_key=api_key)
		model = genai.GenerativeModel(DEFAULT_MODEL)
		response = model.generate_content(prompt, generation_config={
			"temperature": temperature,
			"max_output_tokens": DEFAULT_MAX_TOKENS,
		})
		if hasattr(response, "text"):
			return response.text.strip()
		raise RuntimeError("Unexpected Gemini API response")
	except Exception as exc:
		# If Gemini isn't available (404 / unsupported model) or API key lacks inference
		# permissions, fall back to a local open-source model if possible (free option).
		msg = str(exc)
		logger.warning("Gemini API call failed: %s — falling back to local model", msg)
		try:
			return _call_local_model(prompt, temperature=temperature, max_tokens=DEFAULT_MAX_TOKENS)
		except Exception as e:
			logger.exception("Local model fallback failed: %s", e)
			# re-raise original exception for visibility
			raise


def _call_local_model(prompt: str, temperature: float = 0, max_tokens: int = 512) -> str:
	"""Simple local fallback using Hugging Face Transformers (text-generation).

	This requires `transformers` (and a backend like `torch`). Use a small model
	such as `distilgpt2` to keep resource usage low. The user can
	install dependencies with `pip install transformers torch`.
	"""
	# Avoid torchvision imports when using text-only pipelines
	os.environ.setdefault('TRANSFORMERS_NO_TORCHVISION_IMPORTS', '1')

	try:
		from transformers import AutoModelForCausalLM, AutoTokenizer
		import torch
	except Exception as exc:
		raise RuntimeError(
			"Local fallback unavailable: install transformers and a backend (torch)."
		) from exc

	model_name = get_config_value('LOCAL_FALLBACK_MODEL', 'distilgpt2')
	device = 'cuda' if torch.cuda.is_available() else 'cpu'
	device_index = 0 if device == 'cuda' else -1

	tokenizer = AutoTokenizer.from_pretrained(model_name)
	model = AutoModelForCausalLM.from_pretrained(model_name)
	model.to(device)

	if tokenizer.pad_token_id is None:
		tokenizer.pad_token = tokenizer.eos_token

	inputs = tokenizer(prompt, return_tensors='pt')
	inputs = {k: v.to(device) for k, v in inputs.items()}

	gen_kwargs = {
		'max_new_tokens': max_tokens,
		'do_sample': bool(temperature > 0),
		'temperature': float(temperature),
	}

	with torch.no_grad():
		outputs = model.generate(**inputs, **gen_kwargs)

	input_len = inputs['input_ids'].shape[-1]
	completion_ids = outputs[0][input_len:]
	text = tokenizer.decode(completion_ids, skip_special_tokens=True).strip()
	if not text:
		text = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
	return text



def _extract_json(text: str) -> Dict[str, Any]:
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		match = re.search(r"\{.*\}", text, re.DOTALL)
		if not match:
			raise
		return json.loads(match.group(0))



def decompose_question(question: str) -> Dict[str, Any]:
	content = _call_llm(
		DECOMPOSE_SYSTEM_PROMPT,
		DECOMPOSE_USER_PROMPT.format(question=question),
	)
	return _extract_json(content)



def generate_sql(decomposition: Dict[str, Any]) -> str:
	content = _call_llm(
		GENERATE_SYSTEM_PROMPT,
		GENERATE_USER_PROMPT.format(
			schema=SCHEMA_CONTEXT,
			decomposition=json.dumps(decomposition, indent=2),
		),
	)
	return content.strip().rstrip(';') + ';'



def fix_sql(question: str, sql: str, error: str) -> str:
	content = _call_llm(
		FIX_SYSTEM_PROMPT,
		FIX_USER_PROMPT.format(
			schema=SCHEMA_CONTEXT,
			question=question,
			sql=sql,
			error=error,
		),
	)
	return content.strip().rstrip(';') + ';'
