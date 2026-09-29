# 2026-09-11 이동 연결 현황

## 완료
- 사용자가 BS_Boss_8Way에 Idle_Combat(0,0), Jog_Fwd(0,1), Jog_Bwd(0,-1), Jog_Left(-1,0), Jog_Right(1,0)를 배치했다. 조회로 확인했다.
- ABP_Boss_Crunch EventGraph에서 실제 속도 벡터와 액터의 전방/우측 벡터를 내적하여 MoveForward, MoveRight를 계산한다. 분모는 Max(Speed,30)으로 정지 시 0 나눗셈을 방지한다.
- LocomotionRate는 이동 속도 / LocomotionReferenceSpeed(임시 480cm/s), 범위 0.15~1.5이다. 정지 시에는 1이다. 기준 속도는 발 미끄러짐을 플레이로 측정한 뒤 조정해야 한다.
- 애니메이션 BP 컴파일과 저장 완료. 실제 이동 모션 출력 연결은 아래와 같이 아직 남아 있다.
- 보스 시작 직후 Boss.Combat.Intro 진입을 PIE에서 확인했다. 시작 연출 전체 시각 검증은 미완료이다.

## UI 연결 완료 및 검증
사용자가 ABP_Boss_Crunch의 AnimGraph에 BS_Boss_8Way 플레이어를 추가했다.
MoveRight → X(MoveRight), MoveForward → Y(MoveForward), LocomotionRate → PlayRate 연결을 조회로 확인했다.
포즈 출력은 기존 Save cached pose 'Ground_Loco' 입력에 연결되었다. 나머지 캐시 포즈, 슬롯, IK 연결은 유지된다. 컴파일 및 저장 완료.
PIE에서 Intro 동안 위치 유지 → Observe 동안 위치 유지 → Ready에서 접근 → Attack.Recovery 순서를 확인했다.
실제 접근 중 Speed 약 240cm/s, MoveForward 약 1, MoveRight 약 0, LocomotionRate 약 0.5를 확인했다. 정지 시 방향 값 0, 재생 속도 1로 복귀했다.
8방향 전체의 시각적 발 접지와 기준 속도 480의 보폭 적합성은 아직 플레이 체감 검증이 필요하다. 위 확인은 연결과 실제 전진 값 검증이며 모든 방향의 미끄러짐 해소를 의미하지 않는다.

이전에는 화면 도구 오류로 UI 연결이 막혔으나 사용자의 직접 연결로 해소되었다. PLAN.md의 AnimGraph 직접 리플렉션 편집 금지를 준수했다.
전신 피격 판정 및 팔 공격 판정 수정은 별도 미완료 작업이다.
