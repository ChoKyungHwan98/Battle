# Crunch 런타임 None 오류 수정 — 2026-10-03

## 재현된 오류

`Lvl_Arena_01` PIE 메시지 로그에서 `BP_Boss_Crunch`의 `EventGraph`가 매 프레임 `ActiveAction`을 읽다가 `None에 액세스했습니다`를 반복했다. 이전 로그에는 플레이어 캐릭터가 없는 상태에서 `Set Actor Rotation`의 목표 위치를 계산하다 `CallFunc_GetPlayerCharacter_ReturnValue`가 `None`이 된 오류도 있었다.

## 원인과 수정

- Tick의 돌진 조건은 `bLungeActive AND ... ActiveAction.ActionId ...` 형태였다. 블루프린트 Boolean AND는 단락 평가하지 않으므로 `bLungeActive=false`여도 `ActiveAction.ActionId`를 읽었다. 두 실행 경로가 합쳐지는 지점에 실행형 `Is Valid(ActiveAction)` 매크로를 추가했다. 유효하면 기존 돌진 Branch를 실행하고, 유효하지 않으면 기존 Branch의 false 경로인 회전 판단으로 이어진다.
- `bCanTurn`에서 `Set Actor Rotation`으로 들어가기 전에 실행형 `Is Valid(Get Player Character)`를 추가했다. 플레이어가 아직 없으면 그 프레임의 회전 계산을 건너뛰고, 다음 Tick에서 다시 확인한다.
- 기존 공격 선택, 돌진 계산, 회전 속도와 회복 시간 값은 바꾸지 않았다.

## 검증

- `BP_Boss_Crunch` 컴파일 성공, `EventGraph` 상태 `UpToDate`, 에셋 저장 성공.
- 전투 맵에서 명시적인 PlayerStart 높이로 PIE를 두 차례 실행했다. 첫 실행 약 8초, 두 번째 실행 약 6초 동안 `Saved/Logs/Battle.log`의 블루프린트 런타임 오류 수가 **14,915에서 증가하지 않았다**. 이는 이전 실행들의 누적 오류를 지운 것이 아니라 새 오류가 없었다는 뜻이다.
- 두 번째 실행의 게임 화면에서 보스와 플레이어가 실제로 전투하는 것을 확인했다. 캡처: `Saved/VibeUE/Captures/capture-game-20261003-215554.png`.
