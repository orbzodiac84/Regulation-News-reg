# SSL Verification Matrix — Round 6 Phase 1/2

본 문서는 `config/agencies.json` 에 정의된 9 개 agency 에 대해 `requests.get(..., verify=True)`
가 로컬 및 CI 환경에서 각각 어떻게 동작하는지를 기록하는 매트릭스다. 목적은 `src/config/settings.py`
의 `SSL_VERIFY` 기본값을 `True` 로 전환하기 위한 근거 자료 수집이며, 이 phase 에서는 로컬 결과만
채운다. CI 컬럼은 phase 2 에서 GitHub Actions workflow 가 채우고, `final_decision` 은 phase 3
에서 로컬 + CI 결과를 모두 본 뒤 확정한다.

## 실행 환경

| 항목 | 값 |
|---|---|
| OS | Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39 |
| Python | 3.12.3 |
| requests | 2.33.1 |
| certifi CA bundle | `/home/pacer/projects/reg_brief/venv/lib/python3.12/site-packages/certifi/cacert.pem` |
| 실행 시각 (KST) | 2026-04-08T23:12:09+09:00 |
| 실행자 | Claude Code session (refactor-round6-backend-safety phase 1) |
| 재현 커맨드 | `python3 scripts/ssl_matrix_check.py` |

스크립트는 import 시 부작용이 0 이며 (`if __name__ == '__main__':` 가드), 어떤 대상이 실패해도
전체 실행은 fail-soft 로 완주한다. 결과 원본은 `logs/ssl_matrix_local.json` 에 저장되며 같은
스냅샷을 아래 "원시 결과 스냅샷" 섹션에 그대로 기록해 둔다 (로그 파일은 gitignored 가 될 수 있으므로
증거를 문서 본문에도 함께 남긴다).

## Agency 매트릭스

| agency code | collection_method | target URL | local_ok | local_status | local_error_type | local_error_msg | ci_ok | ci_status | ci_error_type | ci_error_msg | final_decision |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FSC | rss | https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111 | False | — | ConnectionError | `('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))` | TBD | TBD | TBD | TBD | TBD |
| MOEF | rss | https://www.korea.kr/rss/dept_mofe.xml | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |
| FSS | scraper | https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218 | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |
| BOK | scraper | https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1 | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |
| FSS_REG | scraper | https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/list.do?menuNo=200489 | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |
| FSC_REG | scraper | https://www.fsc.go.kr/po040301 | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |
| FSS_REG_INFO | scraper | https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488 | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |
| FSS_SANCTION | scraper | https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476 | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |
| FSS_SANCTION | scraper | https://www.fss.or.kr | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |
| FSS_MGMT_NOTICE | scraper | https://www.fss.or.kr/fss/job/openInfoImpr/list.do?menuNo=200483 | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |
| FSS_MGMT_NOTICE | scraper | https://www.fss.or.kr | True | 200 | — | — | TBD | TBD | TBD | TBD | TBD |

참고: `FSS_SANCTION` / `FSS_MGMT_NOTICE` 는 `url` (list URL) 과 `base_url` (`https://www.fss.or.kr`)
가 서로 다르므로 두 행으로 기록했다. 나머지 scraper agency 는 `url == base_url` 이라 dedup 되어
1 행씩만 기록된다 (RSS 2 개 + scraper 5 개 × 1 + sanction 2 개 × 2 = 11 행).

## 결정 기준

phase 3 에서 각 agency 의 `final_decision` 을 확정할 때 다음 규칙을 따른다:

1. **`local_ok=True AND ci_ok=True`** → `final_decision = "default"`
   - `SSL_VERIFY` 기본값 `True` 를 그대로 사용하고, agency 별 `ssl_verify` 필드 추가 없음.
2. **`local_ok=False OR ci_ok=False`** 이면서 원인이 `SSLError` (cert chain / hostname) 이고,
   **양쪽 환경에서 동일하게 실패** → `final_decision = "opt-out"`
   - 해당 agency 에 한해 `config/agencies.json` 에 `"ssl_verify": false` 필드를 추가하고,
     `http.fetch(..., verify=...)` 를 통해 전달한다.
3. **실패 원인이 `ConnectionError` / `Timeout` 등 네트워크 사유** → `final_decision = "default"`
   - SSL 과 무관하므로 SSL 정책은 건드리지 않는다. 네트워크/소스 다운 이슈는 별도 트래킹.
4. **두 환경 결과가 상반됨 (`env_mismatch`)** → `final_decision = "investigate"`
   - 주석에 사유 (예: "로컬은 성공, GitHub runner 에서만 SSLError") 를 남기고 phase 3 에서
     사람이 판단.

현재 phase 1 결과만 놓고 본다면 `FSC` RSS 엔드포인트가 `ConnectionError` 로 실패했는데, 이는
`SSLError` 가 아니라 TCP reset 계열이므로 규칙 3 에 해당한다. SSL 정책을 `opt-out` 으로 돌릴
근거는 아니다. 다만 phase 2 의 CI 결과에서 동일 원인이 재현되는지, 혹은 실제로는 SSL 관련 원인으로
나타나는지를 교차 확인한 뒤 phase 3 에서 확정한다.

## 재현 방법

- **로컬**: 저장소 루트에서 `python3 scripts/ssl_matrix_check.py` 를 실행한다. 결과는
  `logs/ssl_matrix_local.json` 에 저장되며, stdout 에는 11 행 테이블이 프린트된다.
- **CI**: phase 2 에서 GitHub Actions workflow (`.github/workflows/ssl-matrix.yml` 예정) 가
  동일 스크립트를 돌려 `logs/ssl_matrix_ci.json` 아티팩트를 업로드한다. phase 3 시작 시점에
  아티팩트를 내려받아 본 문서의 `ci_*` 컬럼을 채운 뒤 `final_decision` 을 결정한다.

## 원시 결과 스냅샷 (phase 1 / 로컬 실행)

`logs/ssl_matrix_local.json` 파일이 gitignored 일 수 있어 아래에 전체 내용을 그대로 보존한다.

```json
{
  "run_at_kst": "2026-04-08T23:12:09+09:00",
  "environment": {
    "platform": "Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39",
    "python": "3.12.3",
    "requests": "2.33.1",
    "certifi_ca_bundle": "/home/pacer/projects/reg_brief/venv/lib/python3.12/site-packages/certifi/cacert.pem"
  },
  "results": [
    {
      "code": "FSC",
      "collection_method": "rss",
      "url": "https://www.fsc.go.kr/about/fsc_bbs_rss/?fid=0111",
      "ok": false,
      "status_code": null,
      "elapsed_sec": 0.211,
      "final_url": null,
      "error_type": "ConnectionError",
      "error_msg": "('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))"
    },
    {
      "code": "MOEF",
      "collection_method": "rss",
      "url": "https://www.korea.kr/rss/dept_mofe.xml",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.472,
      "final_url": "https://www.korea.kr/rss/dept_mofe.xml",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.979,
      "final_url": "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "BOK",
      "collection_method": "scraper",
      "url": "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.641,
      "final_url": "https://www.bok.or.kr/portal/singl/newsData/listCont.do?menuNo=201263&pageIndex=1",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_REG",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/list.do?menuNo=200489",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.892,
      "final_url": "https://www.fss.or.kr/fss/job/lrgRegItnPrvntc/list.do?menuNo=200489",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSC_REG",
      "collection_method": "scraper",
      "url": "https://www.fsc.go.kr/po040301",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.834,
      "final_url": "https://www.fsc.go.kr/po040301",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_REG_INFO",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.803,
      "final_url": "https://www.fss.or.kr/fss/job/lrgRegItnInfo/list.do?menuNo=200488",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_SANCTION",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.693,
      "final_url": "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_SANCTION",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 1.393,
      "final_url": "https://www.fss.or.kr/fss/main/main.do?menuNo=200000",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_MGMT_NOTICE",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr/fss/job/openInfoImpr/list.do?menuNo=200483",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 0.991,
      "final_url": "https://www.fss.or.kr/fss/job/openInfoImpr/list.do?menuNo=200483",
      "error_type": null,
      "error_msg": null
    },
    {
      "code": "FSS_MGMT_NOTICE",
      "collection_method": "scraper",
      "url": "https://www.fss.or.kr",
      "ok": true,
      "status_code": 200,
      "elapsed_sec": 1.441,
      "final_url": "https://www.fss.or.kr/fss/main/main.do?menuNo=200000",
      "error_type": null,
      "error_msg": null
    }
  ]
}
```
