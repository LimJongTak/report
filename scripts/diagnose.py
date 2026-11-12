"""환경 진단: API 키, 한컴오피스 자동화, PDF 변환기, 라이브러리 상태."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from reportgen import config  # noqa: E402
from reportgen.library import examples, templates  # noqa: E402
from reportgen.render import pdf  # noqa: E402

print("API 키:", "설정됨" if config.has_api_key() else "없음(.env)")
print("모델:", config.get("llm.model"))
for k, v in pdf.diagnose().items():
    print(f"{k}: {'사용 가능' if v['ok'] else '사용 불가'} — {v['detail']}")
print("양식:", [t["id"] for t in templates.list_templates()])
ex = examples.list_examples()
print(f"과거 사례: {len(ex)}건 (텍스트 정상 {sum(e.get('추출상태') == '정상' for e in ex)}건)")
