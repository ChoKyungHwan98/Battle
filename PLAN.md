# 전투 프로토타입 계획

## 최종 목표

언리얼 5.8에서 플레이어 캐릭터의 이동·락온·더킹·방어·공격을 HFSM으로 구성하고,
세키로식 입력 버퍼와 공격 중 취소 판정을 확장할 수 있는 포트폴리오용 전투
프로토타입을 완성한다.

핵심 성공 기준은 "작동한다"뿐 아니라 다음 네 가지다.

- 상태가 명확하게 분리되어 있을 것
- 블루프린트가 스파게티처럼 연결되지 않을 것
- 새 기능을 추가해도 기존 기능을 뜯어고치지 않을 것
- 기획 의도와 노드 역할을 화면으로 설명할 수 있을 것

## 현재 상태 (2026-08-31 기준)

- `Battle` 프로젝트는 UE 5.8.2 3인칭 템플릿에서 출발했다. 이동·카메라는
  템플릿이 제공하는 `BP_ThirdPersonCharacter` / `BP_ThirdPersonPlayerController`
  / `BP_ThirdPersonGameMode`를 그대로 쓴다 — **이동 시스템을 처음부터 새로
  만들지 않는다.**
- 기존 "포트폴리오" 프로젝트의 `BossArena` 맵·머티리얼·`BP_SkyDome`·
  `BP_TrainingDummy`를 Migrate로 이관 완료했다 (`Content/BossArena/`).
  Player 관련 블루프린트·애니메이션은 전부 버렸다.
- `LevelPrototyping`은 삭제 대상으로 잘못 분류했었다 — 아레나 관중석(Cavea_*)과
  기둥(Colon_Lintel_*) 액터가 `SM_Cube` 등 프로토타이핑 메시를 실제 빌딩
  블록으로 참조하고 있어 **삭제하면 아레나가 깨진다. 계속 유지한다.**
- 템플릿 데모용 `Lvl_ThirdPerson` 맵과 그 전용 자산(`MI_ThirdPersonColWay`,
  해당 World Partition 외부 액터 파일들)은 삭제했다. 에디터/게임 시작 맵을
  `Lvl_Arena_01`로 변경했다 (`Config/DefaultEngine.ini`).
- 지금 실제로 되는 것은 **템플릿 캐릭터의 WASD 자유 이동뿐**이다. 전투용
  캐릭터·HFSM·락온·더킹·공격 중 취소 등은 전부 미착수 상태다.

## 자산 이름과 위치

새 전투 관련 자산은 전부 `/Game/BossArena/Player` 아래에 만든다.
기존(포트폴리오 프로젝트) 레거시 자산은 이 프로젝트로 가져오지 않았으므로
별도 Legacy 폴더가 필요 없다 — Battle 프로젝트 안에서는 모든 것이 새 구조다.

- `Blueprints/BP_Player_Combat`
  - `BP_ThirdPersonCharacter`를 부모로 두거나 그 구성(캡슐·메시·스프링암·
    카메라·무브먼트 컴포넌트 세팅)을 그대로 복제해서 시작하는 새 캐릭터
    블루프린트. 이동 물리는 템플릿 것을 그대로 쓰고, 그 위에 HFSM 상태
    변수와 전투 함수를 얹는다.
- `Blueprints/BP_PlayerController_Combat`
  - 입력 수집과 락온 요청 담당. `BP_ThirdPersonPlayerController`를 참고해
    작성.
- `Blueprints/BP_BossArenaGameMode`
  - `BP_Player_Combat`을 기본 Pawn으로 지정. (기존 이관 때 제외했던 것을
    새로 만든다.)
- `Animation/ABP_Player_Combat`
- `Animation/BlendSpaces/BS_Player_FreeMove`
- `Animation/BlendSpaces/BS_Player_LockOn8Dir`
- `Animation/Montages/AM_Player_Dodge_F` / `_B` / `_L` / `_R`
- `Input/IA_Move`, `IA_Dodge`, `IA_LockOn`, `IMC_Player_Combat`
  (템플릿 `Content/Input`의 `IA_Move`/`IMC_Default`를 참고하되 전투용은
  별도 매핑 컨텍스트로 분리)
- `Data/DA_PlayerCombatTuning`
  - 이동 속도, 회전 속도, 더킹 지속시간, 입력 버퍼 시간 등 튜닝값을
    데이터 애셋으로 관리 (블루프린트에 매직 넘버 박지 않기)

`BP_`는 게임플레이 블루프린트, `ABP_`는 애니메이션 블루프린트. 이름에
역할을 그대로 담아 포트폴리오 화면에서 바로 구분되게 한다.

## 상태 구조

게임플레이 상태와 애니메이션 상태를 분리한다.

```text
MovementMode
├─ Free
└─ LockOn

ActionState
├─ Locomotion
├─ Dodge
├─ Guard
├─ Attack
├─ Hit
└─ Dead
```

기본 우선순위:

```text
Dead/Hit > Dodge > Guard > Attack > Locomotion
```

입력 이벤트는 애니메이션을 직접 재생하지 않는다. `BP_Player_Combat`의
함수만 호출하고, 그 함수가 상태를 바꾸고 애니메이션은 상태를 구독해서
재생한다.

## 단계별 계획

### 1단계 — 플레이어 기본 토대

목표
- `BP_Player_Combat` 생성 (템플릿 캐릭터 구성 재사용)
- `ABP_Player_Combat` 생성
- `BP_BossArenaGameMode`에 새 Pawn 연결, `Lvl_Arena_01` 월드 세팅에 지정
- 기존 템플릿 캐릭터와 완전 분리 (레벨에 중복 스폰 없음)

완료 조건
```
Lvl_Arena_01 실행
→ BP_Player_Combat 생성
→ 카메라 정상
→ 컴파일 오류 없음
```

### 2단계 — 자유 이동

목표
- WASD 자유 이동 (템플릿 무브먼트 컴포넌트 그대로 사용)
- 카메라 기준 이동
- Idle/Move Blend Space 분리
- 이동·회전 속도를 `DA_PlayerCombatTuning`으로 관리

완료 조건
```
W/A/S/D → 원하는 방향으로 이동
입력 해제 → Idle 복귀
```

### 3단계 — 락온 HFSM

목표
```
Free
├─ Idle
└─ Move

LockOn
├─ CombatIdle
└─ CombatMove8Dir
```
- 락온 시 전투 자세, 대상 방향을 바라봄
- 대상 기준 전후좌우 이동, 8방향 Blend Space

완료 조건
- 락온 전/후 Idle 애니메이션이 다름
- 락온 상태에서 8방향 이동, 입력 방향과 애니메이션 방향 일치

### 4단계 — 더킹

목표
```
Locomotion → Dodge → Locomotion
```
- Shift 입력, 입력 방향 저장, 무입력 시 후방 더킹
- 전후좌우 더킹 애니메이션 분리, 더킹 중 이동 입력 차단
- 더킹 종료 후 자동 복귀, 더킹 중 재입력 방지

완료 조건
```
정지 + Shift → 뒤로 더킹
W + Shift    → 앞으로 더킹
A + Shift    → 왼쪽 더킹
D + Shift    → 오른쪽 더킹
```
**회귀 확인 필수**: 이동 중 방향 전환 후 더킹해도 이전 방향으로 고정되지
않아야 한다 (레거시에서 겪었던 문제).

### 5단계 — 세키로식 전투 토대

목표
```
CombatAction
├─ Dodge
├─ Guard
└─ Attack
```
- Attack 상태를 초반(취소 불가)/후반(Guard·Dodge로 취소 가능)으로 분리
- Anim Notify State로 취소 구간·타격 판정 구간 정의
- 상태 우선순위: `Dead/Hit > Dodge > Guard > Attack > Locomotion`

### 6단계 — 입력 버퍼

목표
- 실행 불가능한 입력을 짧게 저장 (기본 0.1초, 최근 입력 1개만 유지)
- 취소 가능 구간 진입 시 예약 행동 실행, 새 입력이 이전 예약을 덮어씀

예시
```
공격 후반 진입 직전 Guard 입력
→ Guard 예약
→ 취소 구간 시작
→ Attack에서 Guard로 전환
```

### 7단계 — 포트폴리오 정리

목표
- 기능별 그래프를 구역으로 정리, 주요 함수·변수에 한국어 주석
- 디버그 화면에 현재 상태·락온·버퍼 표시
- 촬영용 테스트 흐름 구성

최종 영상 흐름
```
자유 이동 → 락온 → 전투 자세 → 8방향 이동 → 방향별 더킹
→ 방어 → 공격 → 공격 중 취소 → 입력 버퍼 실행
```

## 구현 순서 체크리스트

1. `BP_Player_Combat` 생성 (캡슐·메시·카메라 붐·카메라·무브먼트 재사용)
2. `BP_BossArenaGameMode` 생성 후 기본 Pawn 연결, 월드 세팅 지정
3. 입력 구조 구성 (이동/더킹/락온 IA, `IMC_Player_Combat` 등록, 입력↔행동
   함수 분리)
4. 자유 이동 구현 (카메라 기준 이동, Idle/Move Blend Space)
5. 락온 구현 (대상 저장, 대상 방향 회전, 입력 벡터 변환, 8방향 Blend Space)
6. 더킹 구현 (방향 저장, 방향별 몽타주, 입력 차단·재입력 방지, 자동 복귀)
7. `ABP_Player_Combat` 구현 (속도·방향·락온 여부·상태만 전달, 게임플레이
   로직 중복 금지)
8. 확장 토대 (입력 버퍼, 우선순위 정의, Anim Notify State 취소 구간)

## 검증 기준

- 맵 실행 시 `BP_Player_Combat`만 생성되는가 (템플릿 캐릭터 중복 스폰 없음)
- W/A/S/D 자유 이동이 정상인가
- 락온 시 8방향 이동이 정상인가
- 이동 후 Shift를 눌러도 이전 방향으로 고정되지 않는가
- W/A/S/D 각각의 더킹 방향이 정확한가, 무입력 Shift는 후방 더킹인가
- 애니메이션 흐름이 `Locomotion → Dodge → Locomotion`인가
- 더킹 종료 후 캐릭터가 멈추거나 고정되지 않는가
- 블루프린트 컴파일 오류가 없는가
- 모든 주요 함수·변수에 한국어 주석이 있는가
- 포트폴리오 화면에서 기능별 그래프를 쉽게 설명할 수 있는가

## 기본 결정 (변경 시 이 문서를 갱신)

- 이동 물리·카메라는 UE5 3인칭 템플릿 것을 재사용한다. 처음부터 새로
  만들지 않는다.
- 새 기준 플레이어는 `BP_Player_Combat` (`/Game/BossArena/Player`)이다.
- 1차 구현 범위는 이동·락온·더킹이다. 방어·공격·패링·공격 중 회피는 1차
  구조 검증 후 확장한다.
- `LevelPrototyping`은 아레나 지오메트리가 직접 참조하므로 삭제하지 않고
  유지한다.
- `Lvl_ThirdPerson` 데모 맵과 그 전용 자산은 삭제했고, 시작 맵은
  `Lvl_Arena_01`이다.
- 상태 변수는 Enum 하나로 통일한다 (bool 여러 개 + byte 여러 개 동시 사용
  금지).
- 한 이벤트 그래프에 모든 상태 로직을 몰아넣지 않는다 — 상태별 함수/커스텀
  이벤트로 분리한다.
- 플레이스홀더 자산은 검증 전에 영구 배선하지 않는다 (이동+애니메이션부터
  눈으로 확인 후 다음 단계).
- 깔끔한 체크포인트마다 git 커밋한다.
