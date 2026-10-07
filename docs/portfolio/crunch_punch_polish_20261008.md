# 1번 사거리 조정 / 2번 디딤 공격 연결 보정

목표: 사용자가 대략 승인한 1번 디딤 공격의 형태를 유지하며 실제 도달 거리를 확인하고, 2번은 시작과 착지 연결을 다듬는다. 550cm를 무조건 달성하는 대신 자연스러운 디딤으로 가능한 범위를 측정한다.

## 기획자가 볼 결과

| 공격 | 바꾼 것 | 실제 시험 결과 |
|---|---|---|
| 1번 왼손 | 오른발 디딤과 펀치를 유지하면서 몸 전진량을 약 72cm → 117cm로 조정. 대기 자세에서 시작하고, 공격 후 지지발을 조금 일찍 정돈한다. | 400 / 425 / 450cm 명중. 460 / 475cm 빗나감. **현재 권장 최대 450cm.** |
| 2번 오른손 | 대기 자세에서 준비 자세로 연결. 착지 부근 허리 높이가 급하게 바뀌는 부분을 완화. 추가 발걸음이나 펀치 지연은 넣지 않는다. | 350 / 375 / 385cm 명중. 395 / 400 / 420cm 빗나감. 실험실 최대 거리를 **385cm**로 정정. |

거리는 **공격 시작 시 보스와 플레이어의 중심 간 수평 거리**다. 현재 MotionLab의 보스 배율 1.3, 기존 플레이어 충돌 크기와 주먹 접촉 판정을 사용했으며, 정지한 플레이어를 대상으로 측정했다. 이동·회피 중 명중 보장은 아니다. 경계 안의 모든 cm를 검사한 것도 아니다.

550cm를 이 동작에 그대로 요구하면 바닥에 버티는 다리가 과하게 펴진다. 발을 더 멀리 내딛고 몸의 지지 구조를 바꾸는 별도 동작 설계가 필요하다. 허공까지 공격 범위를 키우거나 몸만 슬라이드시키는 방식으로 사거리를 늘리지 않았다.

## 왜 2번 연결을 바꿨는가

기존 2번 첫 자세의 오른손은 대기 자세와 약 103cm 떨어져 있어, 공격이 시작되는 순간 손이 튀어 보일 수 있었다. 첫 0.22초(애니메이션 시간)를 대기 자세에서 연결하도록 키를 작성했다. 실제 타격 구간의 상체 회전과 기존 재생 속도는 유지한다.

착지 구간의 허리 높이 변화도 부드럽게 연결했다. 애니메이션에서 측정한 허리 정지 가속도는 약 176 → 109m/s²로 줄었다. 이는 급격한 변화가 줄었다는 기술 지표이며, 자연스럽다는 미술적 승인과는 구분한다.

## 제작과 검증

- Crunch 자체 원본/승인 클립 → 별도 편집용 복제 → Control Rig 키 → Level Sequence → AnimSequence Bake → 별도 Montage → MotionLab 전용 행동 카드.
- 1번 펀치의 상체 회전 오차는 약 0.034도, 2번은 초기 연결 이후 약 0.015도. 베이크 결과의 발 목표 오차는 두 공격 모두 0.02cm 미만.
- 다리 과신전, 지지 중 발끝 이동, 마지막 프레임, Root Motion, FullBody 전신 적용, 기존 타격/FX Notify 보존을 검사했다.
- 실제 게임에서 1번 몸 전진 약 117cm, 2번 약 69cm를 측정했다. 실제 피해는 명중 시 각 110. 오른손 공격은 hand_r를 별도로 기록했다.
- 두 PIE 시나리오가 통과했고 종료도 확인했다. 두 번째 시나리오는 450cm 명중/460cm 빗나감을 피해량으로 재확인했다. 배경 성능 제한과 임시 미리보기 배우/카메라는 복구했다.
- 기존 승인 모션과 이전 후보는 보존했다. 이번 연결 범위는 **MotionLab 전용**이며 Arena의 Utility/GOAP 선택이나 C++는 이번 작업에서 수정하지 않았다.

## QA 방법

`Lvl_BossMotionLab`에서 시작한다. 기본 선택에서 `L`을 두 번 눌러 **디딤 공격 방식**을 선택하고 `1`, `2`로 비교한다. `J`의 사거리 측정 ON은 거리 제한 없이 공격을 요청하므로 실제 맞는지 확인할 때 사용한다. OFF의 최대 거리 제한과 물리 접촉 거리는 다른 개념이다.

1번은 450cm 부근에서 실제 명중 여부와 지지발이 늘어져 보이는지, 2번은 대기 → 준비의 손 튐과 착지 순간 허리/무릎이 급하게 움직이는지를 확인한다. 자연스러움은 사용자 QA 대기 상태다.

## 출력과 근거

| 구분 | Unreal 경로 |
|---|---|
| 1번 편집 시퀀스 | `/Game/BossArena/Boss/Authoring/LS_Crunch_StepThroughReach90_LeftSwing` |
| 1번 결과 / 몽타주 | `/Game/BossArena/Boss/Authoring/AS_Crunch_StepThroughReach90_LeftSwing` / `AM_Crunch_StepThroughReach90_LeftSwing` |
| 2번 편집 시퀀스 | `/Game/BossArena/Boss/Authoring/LS_Crunch_RightCrossPolished` |
| 2번 결과 / 몽타주 | `/Game/BossArena/Boss/Authoring/AS_Crunch_RightCrossPolished` / `AM_Crunch_RightCrossPolished` |

재현 스크립트: `Tools/TuneCrunchLeftReach.py`, `Tools/PolishCrunchRightPunch.py`, `Tools/TestCrunchPunchPolish.py`.

검증 보고서: `Saved/VibeUE/Reports/crunch_left_reach90_20261008.json`, `crunch_right_polished_20261008.json`, `crunch_punch_contact_20261008.json`.

PIE 기록: `Saved/VibeUE/Scenarios/20261007T164555Z-1F8DECA3.json` / `20261007T164718Z-9D3D8411.json`. 기술 검사 통과와 사용자 품질 승인은 별개다.
