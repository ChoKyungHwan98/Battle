# 플레이어 검 4타: 원본 전진 데이터 복원

사용자 요청: "이동량 복원해줘 전진 데이터".
기준은 설치된 SwordShieldAnimsetPro part2의 원본 Root 이동 데이터다.
DS3에서 추출한 이동량이나 새로 만든 이동 보정이 아니다.

## 변경

각 Battle용 Q_SwordShieldAnimsetPro_part2_Sword_Attack_* 시퀀스의 **root 로컬 Y 위치 키**만 바꿨다.
기존 첫 프레임 위치를 유지하고, 원본 `Root`의 프레임별 전진 변화량을 복사했다.
원본과 대상 모두 30fps, 40키, 1.30초다. 두 에셋의 전진 축이 같은 것을 확인했다.

| 타격 | 원본 클립 | 변경 전 전체 전진 데이터 | 복원 후 전체 전진 데이터 |
|---|---|---:|---:|
| 1 | Sword_Attack_R | 63.80cm | 256.41cm |
| 2 | Sword_Attack_RL | 35.78cm | 143.78cm |
| 3 | Sword_Attack_RLL | 29.41cm | 118.18cm |
| 4 | Sword_Attack_RLLR | 61.76cm | 248.20cm |

위 값은 **각 클립을 끝까지 재생했을 때의 이동 데이터**다.
연계하면 0.55 / 0.3667 / 0.5333초에 다음 타로 넘어가므로 이전 클립의 후반 회복 이동은 재생되지 않는다.
보스나 벽에 붙으면 CharacterMovement 충돌이 이동을 막는다.
이 두 경우를 전진 데이터 자체의 축소와 구분한다.

## 보존 확인

- root의 좌우·높이 위치, 회전·크기는 기존 키를 유지했다.
- 4개 시퀀스의 모든 키 프레임에서 non-root 뼈의 로컬 포즈 해시가 변경 전과 동일했다.
- 원본 ThirdParty 에셋과 공용 Retargeter는 수정하지 않았다.
- 몽타주 구간·재생 배율·Notify·연계 시점, 조작키·카메라·보스 AI는 수정하지 않았다.

## PIE 검증

캡처 없이 시작 위치부터 이동을 측정했고, 실제 몽타주 위치에서의 원본 곡선과 비교했다.

| 단독 공격 | 마지막 관측 위치에서 실측한 전진 |
|---|---:|
| 1타 | 255.29cm |
| 2타 | 143.77cm |
| 3타 | 118.24cm |
| 4타 | 245.71cm |

모든 타격에서 해당 재생 시점의 원본 곡선 대비 오차는 0.01cm 이내였다.
몽타주는 마지막 약 0.08초에 블렌드 아웃하므로 마지막 관측값과 클립 종료 값은 조금 다르다.

- 벽: 앞면 x=170cm인 벽을 향해 1타를 사용했을 때 약 134.90cm에서 정지, 관통 없음.
- 보스: 바닥에 맞춰 배치한 일시적인 Crunch fixture에서 약 33.97cm 전진 후 정지.
  최소 수평 간격 171.03cm, 두 캡슐 반경의 합 171.50cm로 통과하지 않았다.
- 최초 보스 fixture의 고정 높이 오프셋이 Crunch를 공중에 띄워 수평 간격 검사가 실패했다.
  **검사 fixture의 바닥 높이만 수정**해 다시 통과했다. 배치된 실제 레벨 보스는 수정하지 않았다.
- 4타 LMB 연계와 시각 확인은 별도의 시나리오로 검사했다.

## 파일·근거·롤백

- 적용: `Tools/RestoreSwordForwardMotion.py` (PIE 종료 후 prepare → apply).
- 검사: `Tools/TestSwordForwardMotion.py`, `Tools/TestReferenceSwordCombo.py`.
- 변경 전 키: `Saved/VibeUE/sword-forward-before.json`.
- 데이터 비교: `Saved/VibeUE/sword-forward-restored.json`.
- 실제 이동·충돌: `Saved/VibeUE/sword-forward-pie.json`.
- `20260929T163953Z-E976B0A6`: 단독 4타·벽 통과, 최초 보스 fixture 검사 실패.
- `20260929T164123Z-858144CA`: 바닥에 맞춘 보스 fixture 검사 통과.
- `20260929T164154Z-07E699F1`: 4타 LMB 연계 검사.
- 복원 전 커밋 `201c592`의 네 Q 시퀀스만 복구하면 이전 전진량으로 돌아간다.
