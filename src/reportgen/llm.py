"""Claude API 래퍼 (GEN-08, NFR-07~09).

- 모델·토큰·effort는 config/settings.yaml
- API 오류: SDK 내장 지수 백오프 재시도(max_retries)
- JSON 형식 오류: 오류 내용을 붙여 최대 json_retries회 재요청
- 모든 호출의 프롬프트·응답을 work/logs/에 저장(마스킹 적용 후 내용)
"""
from __future__ import annotations

import base64
import io
import json
import re
import time
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel, ValidationError

from . import config


class LLMUnavailable(RuntimeError):
    """API 키 없음 등으로 AI를 호출할 수 없음."""


class LLMError(RuntimeError):
    pass


_client = None


def client():
    global _client
    if not config.has_api_key():
        raise LLMUnavailable("ANTHROPIC_API_KEY가 설정되지 않았습니다(.env 파일).")
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(max_retries=int(config.get("llm.max_retries", 4)), timeout=600)
    return _client


# ---------- 프롬프트 템플릿 ----------

def load_prompt(name: str) -> tuple[str, str]:
    """prompts/<name>.md 를 읽어 (system, user템플릿) 반환. '## USER' 줄로 구분."""
    text = (config.path("prompts") / f"{name}.md").read_text(encoding="utf-8")
    if "\n## USER" in text:
        sys_part, user_part = text.split("\n## USER", 1)
        user_part = user_part.split("\n", 1)[1] if "\n" in user_part else ""
    else:
        sys_part, user_part = text, ""
    sys_part = re.sub(r"^## SYSTEM\s*\n", "", sys_part.strip())
    return sys_part.strip(), user_part.strip()


def render(template: str, variables: dict[str, Any]) -> str:
    """<<변수>> 치환 (HWPX의 {{필드}}와 겹치지 않게 << >> 사용)."""
    def repl(m):
        v = variables.get(m.group(1).strip(), "")
        return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=1)
    return re.sub(r"<<([^<>]+)>>", repl, template)


# ---------- 호출 ----------

def _log(log_dir: Path | None, tag: str, payload: dict) -> None:
    if not log_dir:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    fn = log_dir / f"{time.strftime('%Y%m%d_%H%M%S')}_{re.sub(r'[^0-9A-Za-z가-힣_]+', '_', tag)[:60]}.json"
    fn.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def call(system: str, content: list | str, *, max_tokens: int | None = None, log_dir: Path | None = None,
         tag: str = "call") -> tuple[str, dict]:
    """메시지 1회 호출 → (텍스트, usage)."""
    import anthropic

    c = client()
    kwargs: dict[str, Any] = dict(
        model=config.get("llm.model", "claude-sonnet-5-5"),
        max_tokens=int(max_tokens or config.get("llm.max_tokens", 16000)),
        system=system,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": config.get("llm.effort", "medium")},
    )
    try:
        if config.get("llm.refusal_fallback", True):
            resp = c.beta.messages.create(**kwargs, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        else:
            resp = c.messages.create(**kwargs)
    except anthropic.AuthenticationError as e:
        raise LLMUnavailable("API 키가 올바르지 않습니다.") from e
    except anthropic.BadRequestError as e:
        raise LLMError(f"요청 오류: {e.message}") from e
    except anthropic.RateLimitError as e:
        raise LLMError("API 사용 한도를 초과했습니다. 잠시 후 다시 시도하세요.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"API 오류({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("네트워크 연결 오류. 인터넷 연결을 확인하세요.") from e
    if resp.stop_reason == "refusal":
        raise LLMError("모델이 요청을 거절했습니다(안전 정책).")
    text = "".join(getattr(b, "text", "") for b in resp.content if b.type == "text")
    usage = {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens}
    _log(log_dir, tag, {"model": kwargs["model"], "system": system,
                        "user": content if isinstance(content, str) else "[멀티모달]",
                        "response": text, "usage": usage, "stop_reason": resp.stop_reason})
    if resp.stop_reason == "max_tokens":
        raise LLMError("응답이 최대 길이에서 잘렸습니다. settings.yaml의 llm.max_tokens를 늘려 주세요.")
    return text, usage


def parse_json(text: str) -> Any:
    """응답에서 JSON 본문 추출."""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = m.group(1) if m else text
    start = min([i for i in (body.find("{"), body.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("JSON을 찾을 수 없음")
    end = max(body.rfind("}"), body.rfind("]"))
    return json.loads(body[start:end + 1])


def call_json(prompt_name: str, variables: dict[str, Any], model: Type[BaseModel] | None = None, *,
              log_dir: Path | None = None, tag: str | None = None, max_tokens: int | None = None) -> tuple[Any, dict]:
    """GEN-08 JSON 응답 호출. 형식이 깨지면 오류를 알려주고 최대 json_retries회 재요청."""
    system, user_t = load_prompt(prompt_name)
    user = render(user_t, variables)
    tries = int(config.get("llm.json_retries", 2)) + 1
    usage_total = {"input": 0, "output": 0}
    last_err = ""
    for k in range(tries):
        msg = user if not last_err else (
            user + f"\n\n[이전 응답 오류]\n{last_err}\n위 오류를 고쳐 JSON만 다시 출력하세요.")
        text, usage = call(system, msg, max_tokens=max_tokens, log_dir=log_dir, tag=f"{tag or prompt_name}_{k}")
        usage_total = {key: usage_total[key] + usage[key] for key in usage_total}
        try:
            data = parse_json(text)
            if model is not None:
                data = model.model_validate(data).model_dump()
            return data, usage_total
        except (ValueError, ValidationError) as e:
            last_err = str(e)[:1500]
    raise LLMError(f"AI 응답 JSON 형식 오류({tries}회 시도): {last_err[:300]}")


def call_text(prompt_name: str, variables: dict[str, Any], *, log_dir: Path | None = None,
              tag: str | None = None) -> tuple[str, dict]:
    system, user_t = load_prompt(prompt_name)
    return call(system, render(user_t, variables), log_dir=log_dir, tag=tag or prompt_name)


# ---------- 비전: 깨진 PDF 쪽 읽기 (ING-05/예외처리) ----------

def read_pdf_pages(path: str | Path, pages: list[int], log_dir: Path | None = None) -> list[tuple[int, str]]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    out = []
    for i in pages:
        im = pdf[i - 1].render(scale=1.6).to_pil().convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        text, _ = call(
            "당신은 한국어 공문서를 정확히 옮겨 적는 전사기입니다. 보이는 글자만 그대로 옮기고 추측하지 마세요.",
            [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
             {"type": "text", "text": "이 쪽의 모든 글자를 읽는 순서대로 옮겨 적으세요. 표는 마크다운 표로, "
                                      "그림/차트는 [그림: 짧은 설명]으로 표시하세요. 설명 없이 내용만 출력하세요."}],
            log_dir=log_dir, tag=f"vision_p{i}")
        out.append((i, text.strip()))
    return out


def caption_image(path: str | Path, log_dir: Path | None = None) -> str:
    """ING-05 사진 캡션 초안."""
    from PIL import Image

    im = Image.open(path).convert("RGB")
    im.thumbnail((1200, 1200))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    b64 = base64.standard_b64encode(buf.getvalue()).decode()
    text, _ = call("행사 결과보고서용 사진 설명을 씁니다. 보이는 것만 쓰고 사람 이름은 추측하지 마세요.",
                   [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": "이 사진을 20자 이내 명사형 캡션으로 쓰세요(예: 현직자 멘토링 진행 모습)."}],
                   max_tokens=2000, log_dir=log_dir, tag="caption")
    return text.strip().splitlines()[0] if text.strip() else ""


def estimate_cost(input_chars: int, n_calls: int, out_tokens_per_call: int = 1200) -> dict:
    """NFR-11 대략적 토큰·비용 추정 (한글 1자 ≈ 1토큰 보수적 가정)."""
    price = config.get("llm.price_per_mtok", {"input": 2.0, "output": 10.0})
    tin = input_chars
    tout = n_calls * out_tokens_per_call
    usd = tin / 1e6 * price["input"] + tout / 1e6 * price["output"]
    return {"input_tokens": tin, "output_tokens": tout, "usd": round(usd, 3)}
