# 현재 카메라·락온 적용 결과

2026-09-29. 목표는 **DS3의 기본 자유 시점과 락온 동작을 재현하고, 큰 보스를 상대하는 구도는 군다를 참고하는 것**이다. 이전의 임의 근접 줌 보정을 기준으로 삼지 않는다. 조작키는 그대로 유지했다.

## 적용한 것

| 상황 | 실제 동작 |
| --- | --- |
| 자유 시점 | 기준 거리 400cm, 발 기준 피벗 높이 142cm, 마우스로 회전 |
| 보스 락온 | 기준 거리 550cm, 피벗 높이 182cm, 보스 몸통을 추적. 구르기·공격 중에도 카메라 추적 유지 |
| 화각 | 수직 43°. 화면 비율에 맞춰 수평 화각 변환. 달리기 자체로 화각을 바꾸지 않음 |
| 근접 | 거리에 따라 최대 250cm를 더하던 보정은 실행 경로에서 제외. 3m·6m·10m 락온에서도 기준 거리 550cm |
| 표식 | 보스의 `spine_03` 위치에 작은 흰색 점. 카메라와 같은 `LockAimPoint`를 사용하고 화면 DPI를 반영해 투영 |
| Space 달리기 | 기존 즉시 구르기/홀드 달리기 유지. 실제 홀드 트리거 발동 시 대상 추적과 표식 해제, 자유 방향 이동. 카메라 거리·높이는 직전 락온 프로필 유지 |
| 달리기 종료 | 이전 합의대로 같은 대상에 락온 복귀. 대상이 죽었거나 15m 밖이면 복귀하지 않고 저장 타깃 폐기 |
| 마우스 가운데 | 락온/해제. 획득 가능한 대상이 없으면 플레이어 뒤로 카메라 방향 리셋. 현재 피치 유지 |
| 타깃 선택 | 살아 있고, 설정 거리 안에 있고, 카메라 앞이며 시선이 닿는 보스만 획득. 현재 단일 보스 대상 |
| 대상 사망·거리 이탈 | 락온과 표식 해제. 죽은 대상 재획득 차단 |
| 벽 | SpringArm 충돌로 카메라가 벽을 통과하지 않도록 당김. 장애물 제거 후 복원. 보스·플레이어 몸체는 Camera 채널을 막지 않음 |

## 원본 근거와 재현 범위

설치된 DS3의 `Data0.bdt`를 읽기 전용으로 분석했다. 원본 변경은 없다. SHA-256은 `955016ab940f0e3526b7ef9e29cff7b498e032939023b50b5d5a172832582b87`이다.

| 필드 | 기본 행 0 | 선택한 행 5110 |
| --- | ---: | ---: |
| `CamDistTarget` | 4.0m | 5.5m |
| `chrOrgOffsetZ` | 1.42m | 1.82m |
| `FovYChange` | 43° | 43° |
| `lockRotXShiftRatio` | 0.45 | 0.20 |
| `rotRangeMinX` | −40° | −25° |
| `chrLockRangeMaxRadius` | 15m | 15m |

- [Paramdex DS3 필드 정의](https://github.com/soulsmods/Paramdex/blob/master/DS3/Defs/LOCK_CAM_PARAM_ST.xml): 표의 형식과 단위 근거.
- [Souls Modding 군다 설명](https://soulsmodding.com/doku.php?id=tutorial:boss-iudex-gundyr): 군다의 모델 번호가 `c5110`임을 확인. **5110 카메라 행의 군다 이벤트 연결은 아직 직접 추출하지 않았으므로, 이 모델 번호와 대응하는 행을 선택한 것은 추론이다.**
- `ReadDS3GundyrCamera.py`로 NPC 511000/511100의 `lockCamParamId=-1`, `lockDist=10`을 확인했다. 카메라 최대 반경과 NPC 거리 필드가 원작 코드에서 어떻게 조합되는지는 미확인이다. 현재 Battle은 카메라 행의 15m를 획득·유지 한계로 사용한다.
- [DS3 공식 조작 설명](https://www.fromsoftware.jp/manual/darksouls3/win/operation.html): 같은 버튼의 락온/카메라 리셋 동작 근거.
- [The Grand Archives 카메라 도구](https://github.com/The-Grand-Archives/Dark-Souls-III-CT-TGA): 카메라 파라미터와 자동 추적 등의 역공학 참고. 치트 테이블은 텍스트만 조사했고 실행하지 않았다.

카메라 거리·높이·화각·편향은 실제 데이터 값이다. 원작 내부 보간식, 피치 좌표계, 충돌 공식, 시선 가림 유예 시간은 확정되지 않았다. UE의 거리 전환 300cm/s, 높이 전환 150cm/s, 회전 보간 10, SpringArm 충돌, 몸통 소켓 선택, 표식 렌더링과 질주 중 프로필 유지는 Battle에서 재현한 규칙이다. 자유 시점의 자동 회전 보정, 여러 타깃 전환, 원작 카메라 흔들림 곡선은 DS3와 일치한다고 검증한 항목이 아니다.

## 검증

| PIE 시나리오 | 결과 |
| --- | --- |
| `20260929T045507Z-A95B8384` | 3m·6m·10m 락온, 자유 시점 거리·뼈 화면 위치 기록 및 캡처 통과 |
| `20260929T045925Z-8FADABBD` | 실제 MMB/Space 입력으로 표식 위치·표시/숨김, 달리기 해제/복귀, 거리·사망 해제, 타깃 없는 카메라 리셋, 수직 화각 검사 통과 |
| `20260929T050035Z-31628E79` | 자유 시점 벽 충돌 및 복원 통과 |
| `20260929T050109Z-07C88C9B` | 달리기 중 거리 밖으로 이동한 저장 타깃 복귀 차단 통과 |

3m 락온의 측정 화면 비율은 보스 머리 y=0.207, 발 y=0.782, 플레이어 발 y=0.874였다. 실행 화면에서 표식과 구도를 직접 확인했다. 최종 `BP_Player_Combat`와 `WBP_PlayerHUD`는 오류 0으로 컴파일 및 저장했다.

## 어디에 구현됐나

- `BP_Player_Combat.UpdateCameraFraming`: 거리·월드 피벗 높이·화각. 이전 근접 보정 노드는 비교/롤백용으로 남겨 두고 실행 경로에서 제외.
- `UpdateLockOnRotation`: 애니메이션 몸통 좌표를 `LockAimPoint`에 저장하고 카메라 추적. 생존·거리 조건 검사.
- `ToggleLockOn`: 대상 획득 조건과 타깃이 없는 카메라 리셋.
- `SetSprinting`: 달리기 동안 타깃 저장/해제, 종료 시 복귀 조건.
- `WBP_PlayerHUD.EventGraph`: 같은 `LockAimPoint`를 화면 좌표로 바꿔 `LockOnMark` 표시. 유효한 락온이 없으면 숨김.
- 구현 도구 `Tools/ApplyDS3CameraPolish.py`, 검증 도구 `Tools/TestDS3CameraPolish.py`.

백업: `/Game/BossArena/Backup/BP_Player_Combat_PreCameraSprint_20260929`, `/Game/BossArena/Backup/WBP_PlayerHUD_PreLockMark_20260929`. 작업 실행 기록: `20260929T023834Z-21938014`.
