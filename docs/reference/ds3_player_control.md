# DS3 플레이어 조작·카메라 참조 사양과 Battle 적용

2026-09-29. 수치의 출처를 **DS3 게임 파일에서 읽은 카메라 값**, **사용자가 준 조작 참고 텍스트**, **Battle용 조정값**으로 구분한다. 현재 Battle의 조작키는 유지한다.

## 1. 출처와 해석 범위

- Steam 설치본 `DARK SOULS III/Game/Data0.bdt`의 `LOCK_CAM_PARAM_ST` 141행을 읽기 전용으로 추출했다. 원본 파일 SHA-256: `955016ab940f0e3526b7ef9e29cff7b498e032939023b50b5d5a172832582b87`. 추출 코드: `Tools/ReadDS3Camera.py`; 로컬 전체 추출: `Saved/VibeUE/ds3-camera-rows.json`.
- 필드 이름과 형식: [soulsmods/Paramdex의 DS3 LOCK_CAM_PARAM_ST 정의](https://github.com/soulsmods/Paramdex/blob/master/DS3/Defs/LOCK_CAM_PARAM_ST.xml). [Souls Modding의 TAE 설명](https://soulsmodding.com/doku.php?id=format:tae), [DSAnimStudio](https://github.com/Meowmaritus/DSAnimStudio)는 애니메이션 이벤트와 취소·무적·추적 구간을 설계하는 구조적 참고 자료다.
- 카메라 행에는 대상 이름이 들어 있지 않다. **0번을 일반 카메라, 1000번을 큰 보스 락온에 사용하기로 한 것은 Battle의 선택**이다. 이 두 행이 원작에서 해당 상황에 실제로 쓰였다는 NPC 매핑은 확인하지 못했다.
- 첨부된 R1의 `0.100`, `0.300`, `0.470` 등의 시각은 설명용 예시다. 원본 `c0000` TAE와 루트 모션은 아직 추출하지 않았으므로 Battle 공격 시간을 원작 실측치라고 부르지 않는다.

## 2. 카메라 원본 수치 → Battle 설정

| 필드 | 행 0 | 행 1000 | Battle 적용 |
| --- | ---: | ---: | --- |
| `CamDistTarget` | 4.0m | 6.0m | 자유 이동 400cm, 락온 600cm. 300cm/s로 전환 |
| `FovYChange` | 43° | 43° | 뷰포트 종횡비에 맞춰 수평 FOV로 변환하여 수직 43° 유지 |
| `chrOrgOffsetZ` | 1.42m | 1.42m | 플레이어 발 기준 카메라 피벗 약 142cm. 캡슐 중심 90cm + 붐 타깃 오프셋 52cm |
| `rotRangeMinX` | −40° | −40° | 락온 카메라 피치 하한 −40° |
| `lockRotXShiftRatio` | 0.45 | 0.40 | 큰 보스 구도에 0.40 사용. 타깃을 향한 피치에서 수직 FOV 기준 편향 각도 계산 |
| `chrLockRangeMaxRadius` | 15m | 15m | 획득 거리 1500cm |

원작의 피치 제한 좌표계와 카메라 내부 보간식은 확인되지 않았다. 따라서 피치 상한 +25°, 락온 해제 거리 2000cm, 회전 보간 10, 위치 랙 최대 60cm와 부분 틱 계산은 **Battle 조정값**이다. 획득 15m와 해제 20m를 분리한 이유는 제자리 뒤구르기 한 번만으로 락온이 끊기지 않게 하기 위해서다. 벽에서는 SpringArm의 기존 카메라 충돌이 거리를 줄인다.

화면이 1793×855일 때 수직 43°는 수평 약 79.1°가 된다. 16:9에서는 약 70.0°다. `CameraComponent`는 Maintain X FOV로 설정하고, `UpdateCameraFraming`에서 실제 뷰포트 비율에 맞춰 수평값을 넣는다. `UpdateLockOnRotation`은 카메라 위치에서 보스를 향한 피치와 화면 편향을 계산한다. 락온이 아닌 상태에서는 사용자 카메라 피치를 그대로 둔다.

## 3. 입력 → 상태 → 애니메이션 → 구간 → 다음 행동

| 단계 | 현재 Battle 동작 | 위치 / 값 |
| --- | --- | --- |
| 입력 | WASD, F 점프, Space 즉시 구르기·0.25초 길게 누르면 달리기, LMB 4타, RMB 가드, MMB 락온 | 기존 Enhanced Input 유지 |
| 상태 | Locomotion / Dodge / Guard / Attack / Hit 구분. 피격은 예약 행동을 지운다 | `BP_Player_Combat.ActionState` |
| 구르기 | 시작 방향 확정, 0.433초 무적, 0.56초 320cm 이동, 0.70초 종료 | `TryEnterDodge`, `UpdateDodgeMovement` 등. 26F/42F @60fps는 첨부 텍스트의 참고값; 이동거리는 Battle 값 |
| 공격 전진 | 공격 애니메이션의 기존 루트 키를 XY 25%로 줄인 뒤 루트 모션 활성화. 일반 `AddMovementInput`은 공격 중 차단 | 4개 `Q_SwordShieldAnimsetPro_part2_Sword_Attack_*`. 첫 타 약 62cm, 다음 약 36/29/58cm의 **에셋상** 1.1초 지점 이동량 |
| 방향 보정 | 공격 시작 후 재생 길이의 첫 10%에만 최대 360°/s로 타깃/입력 방향 보정. 그 뒤 몸 방향 고정, 락온 카메라는 계속 추적 | `UpdateAttackSteering`; 10%와 속도는 Battle 값 |
| 칼 판정 | 공격 시작의 12%에 판정 시작, 30% 길이의 칼 궤적 검사. 한 대상 한 타 1회 | `DoAttackHitCheck`, `TraceSwordWindow`; Battle 값 |
| 구르기 취소 | 공격 길이 60%에 별도 구르기 창을 열고 예약 구르기를 실행 | `OnAttackRollWindowOpen`; Battle 값 |
| 4타 연계 | 공격 길이 68%에 다음 공격 창을 연다 | `OnComboWindowOpen`; Battle 값 |
| 입력 예약 | 허용된 공격/구르기 **하나**. 나중에 받아들인 입력이 이전 것을 지움. 0.85초 뒤 미소비 예약 폐기 | `TryEnterAttack`, `TryEnterDodge`, `UpdateActionRequests`; Battle 값 |
| 가드 홀드 | RMB를 계속 누르면 공격·구르기 종료 후 Locomotion에서 가드 시작. 중간에 떼면 요청 폐기 | `bGuardRequested`, `UpdateActionRequests` |
| 달리기 락온 | Space 홀드 트리거가 실제 발동할 때 락온 일시 해제, 종료 시 같은 대상 복귀 | 기존 `SetSprinting` 유지 |

공격 판정, 회전, 구르기 취소, 연계 입력, 회복 종료는 서로 다른 구간이다. 현재는 블루프린트 타이머가 길이를 기준으로 열고 닫는다. TAE와 같은 데이터 에셋/AnimNotifyState로 완전히 옮긴 것은 아니다. 구르기는 기존 캡슐 Sweep 곡선이므로 원작 구르기 루트 모션도 아직 적용되지 않았다.

## 4. 차이 분석과 다음 계측

| 항목 | 이번에 확인한 것 | 남은 원본 데이터 |
| --- | --- | --- |
| 카메라 거리·수직 FOV·원점 높이 | 설치된 DS3 `LOCK_CAM_PARAM_ST` 실제 행 | 보스별 행 매핑, 카메라 내부 보간/충돌 공식 |
| 회피 | 첨부 텍스트의 26F/42F를 목표로 PIE에서 0.433/0.70초 검증 | 원본 `c0000` 구르기 모션 루트 곡선과 TAE |
| 공격 | Battle 검·방패 에셋 루트 이동, 단계별 판정/회전/취소 분리 | DS3 R1-1/R1-2의 TAE 입력·판정 프레임, 원본 루트 이동량 |
| 입력 버퍼 | 한 행동 예약, 교체·소비·만료 규칙 | HKS의 정확한 우선순위·만료 규칙 |
| 피격/가드 | 기존 Battle 피격·가드 상태와 이번 홀드 요청 | 장비 중량, 방패 안정성 등 원본 파라미터 |

실제 원작 타임라인을 확보하기 전까지 10%·12%·30%·60%·68%와 0.85초를 DS3 수치라고 홍보하지 않는다. 포트폴리오 설명에서는 **원작 자료를 관찰해 행동을 단계별로 분해하고, Battle의 에셋과 보스 크기에 맞춰 다시 계측한 구현**이라고 기술한다.

## 5. 변경·검증 기록

- 구현 스크립트: `Tools/PolishDS3CameraControl.py`의 `apply()`를 Unreal Python에서 PIE 종료 후 호출한다. 플레이어 블루프린트와 4개 공격 시퀀스의 변경 전 백업은 `/Game/BossArena/Backup/*_PreDS3Camera_20260929`. 루트 키 25% 변환은 이번에 백업을 만든 후 Editor Python 컨트롤러로 한 번 적용했으며 `apply()`는 저장된 시퀀스를 다시 변환하지 않는다.
- 검증 스크립트: `Tools/TestDS3CameraControl.py`와 기존 `Tools/TestSwordShield.py`, `Tools/TestSoulsHits.py`.
- PIE: 자유 카메라/공격 궤적 10개 (`20260928T162801Z-7BDD9005`), 락온·가드 홀드 12개 (`20260928T163252Z-8EA4ED71`), 분리 취소 창 10개 (`20260928T164119Z-389B14B2`), 초반 추적·후반 고정 9개 (`20260928T164255Z-9607D4D6`), 락온 획득·해제 거리 13개 (`20260928T164841Z-11A46CE3`), 기존 공격·피격·구르기 21개 (`20260928T163734Z-264B07C6`), 락온 달리기 15개 (`20260928T163156Z-46E56F64`), 칼/보스 판정 38개 (`20260928T164334Z-EC0C066D`). 총 128개 검사 통과. 모든 시나리오는 `LogScript: Warning` 부재도 검사했다.
- 플레이 화면 캡처에서 일반 카메라와 락온 복귀 시 플레이어·보스 위치를 직접 확인했다. 블루프린트 최종 상태는 `BS_UP_TO_DATE`다.
