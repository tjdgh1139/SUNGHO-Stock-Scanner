# ATLAS 장전 오프라인 검증 게이트 (2026-10-17)

이 문서는 실거래 주문을 허용하지 않는 RC15 검증 체크리스트입니다. **main 및 Streamlit 배포를 변경하지 않습니다.**

## 장이 열리기 전 실행
```bash
python -m compileall -q app.py atlas_paper_sqlite.py atlas_paper_live_panel.py atlas_paper_live_bridge.py
python -m pytest -q test_atlas_paper_sqlite.py test_atlas_paper_feed_health.py test_atlas_paper_live_bridge.py test_atlas_paper_live_smoke.py test_atlas_paper_ledger.py test_atlas_paper_store.py test_atlas_ws_panel.py test_atlas_preopen_rollover.py test_regression.py
```

## 합격 조건
- 인증되지 않았거나 10초보다 오래된 KIS 체결은 신호·가상체결 생성 금지
- 소켓 연결만 성공한 상태를 실시간 체결 확인으로 표시하지 않음
- 같은 틱 재수신·Streamlit 재실행에도 SIGNAL/FILL/OUTCOME 중복 저장 없음
- SQLite 재시작 복구 후 신호 수 제한은 날짜별로 적용
- 영구 볼륨이 없으면 기록 보존을 보장하지 않으며 UI에 경고
- 미국 후보는 인증된 미국 체결 피드 연결 전 가상 체결 금지
- 모든 신호는 PAPER_ONLY, 실제 주문 API 호출 금지
- 당일 수동 후보는 자동 갱신으로 덮어쓰지 않음

## 장중에만 검증 가능한 항목
- KRX/NXT 시장별 실제 체결 시각, 데이터 신선도 및 종목 커버리지
- 장전 A 후보 고정 / 장중 B 후보 교체, 체결 후 1·3·5·30분 평가
- 네트워크 단절·재연결·장 전환 시 누락 및 중복 여부
- 실제 관찰된 가상 손익(수수료·슬리피지 포함), 체결 미확인과 0건 구분

## 현재 제한
브라우저를 닫으면 Streamlit fragment 기반 신규 관찰이 멈춥니다. SQLite 설정은 이미 발생한 이벤트 보존용이며 24시간 수집기를 대신하지 않습니다. 별도 상시 수집기와 영구 저장 볼륨, 실시간 운영 확인이 필요합니다.
