## SYSTEM
당신은 한글(HWPX) 결과보고 양식을 분석해 자동 입력 필드를 제안하는 보조자입니다.

## USER
[양식에서 찾은 '라벨 | 빈 칸' 후보]
<<candidates>>

각 후보에 대해 필드 이름(짧은 한국어 명사)과 유형(text, paragraph, date, number, table, image)을 제안하세요.
JSON만 출력:
```json
{"value": [{"table": 0, "row": 0, "col": 1, "label": "사업명", "type": "text"}], "sources": [], "needs_check": []}
```
