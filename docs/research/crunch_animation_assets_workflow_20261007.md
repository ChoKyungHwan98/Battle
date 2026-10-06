# Crunch 모션 제작·에셋 부족 대응 조사

조사일: 2026-10-07. 대상: Unreal Engine 5.8.3 / VibeUE 5.0.

## 결론

**사용자 후속 지시로 제작 범위를 변경했다. Mixamo, 외부 모캡, 다른 캐릭터의 애니메이션을 Crunch의 소스로 사용하지 않는다.**
허용되는 것은 Crunch 원본 편집과 Crunch 스켈레톤에 직접 만든 키프레임 모션이다.
우선순위는 **Crunch 편집용 리그 검증 → Crunch 원본을 바탕으로 핵심 자세 직접 제작 → 동작 연결·접지 보정 → 정상 속도 영상 검수 → 실제 사거리 검사**다.
아래 외부 모션 팩·FightAnimations/UAF 후보·리타깃 권장은 이전 조사 기록이며 현재 제작안에서 제외한다.
현재 오른발 디딤 공격의 품질 문제를 새로운 AI 플러그인이나 큰 애니메이션 팩 구매로 바로 해결한다고 보지 않는다.
이 절차가 한 공격에서 성공하면 이후 공격 제작의 반복 절차로 채택한다. 아직 검증된 제작 표준은 아니다.

현재 제작안은 [Crunch 전용 직접 제작 계획](../portfolio/crunch_hand_authored_motion_plan_20261007.md)을 따른다.

## 조사 범위와 한계

- 웹 검색 후 제작자·Epic·제품 제작사의 공개 페이지를 확인했다. 강의 설명, 제공된 챕터, 프로젝트 자료, 현재 공식 문서를 검토했다.
- 아래 YouTube 주소는 영상 식별자와 YouTube oEmbed의 실제 제목·제작자를 대조했다.
- YouTube 본문 접근 일부는 제한됐고 전체 영상 재생·전체 자막 검토는 수행하지 않았다. 내용 적합성은 공개 강의 설명과 챕터에 근거한 판단이다.
- 자료의 발행일과 사용 엔진 버전을 분리한다. 2026년 영상이라고 모두 UE 5.8 전용은 아니다.
- 에디터는 사용자 PIE 실행 중이었다. 플레이·에셋을 변경하지 않고 Asset Registry의 **저장된 이름·종류 메타데이터만** 조회했다. 후보 모션을 재생하거나 뼈·루트 이동 데이터를 읽지 않았다.

## 가장 맞는 영상·강의

### 1. 기존 Crunch 펀치를 편집하는 절차 — 최우선

**Baking Animation in UE5: Control Rig to Animation Sequence & Back!**

- 제작자: Unreal Engine 공식 채널 / Sir Wade 관련 강의.
- YouTube 공개일: 2026-01-14.
- [영상](https://www.youtube.com/watch?v=mDEliLixziU)
- 주제: 기존 Animation Sequence와 편집 가능한 Control Rig 키 사이의 변환. Backwards Solve와 베이크를 다룬다.
- 적용: 기존 왼손 공격을 발·골반·손을 조절할 수 있는 편집 대상으로 바꾸고, 수정 결과를 게임용 시퀀스로 저장하는 기초다.
- 조건: Crunch와 호환되는 편집용 리그가 필요하다. 마네킹 리그를 그대로 Crunch에 적용할 수 있다는 뜻은 아니다.

**NON-DESTRUCTIVE Animation in UE5! Layered Control Rigs Explained**

- 제작자: Unreal Engine 공식 채널.
- YouTube 공개일: 2026-01-16.
- [영상](https://www.youtube.com/watch?v=A8U_8iPc5hA)
- 주제: 기존 모션을 보존하면서 별도 수정 키를 얹고, 수정 효과를 켜고 끄며 비교한다.
- 적용: 원래 왼손 모션과 오른발 디딤 수정안을 같은 조건에서 비교하기 좋다.
- 조건: 레이어 방식에는 동작하는 Backwards Solve가 필요하다. 원본 보존만으로 수정 품질이 보장되지는 않는다.

관련 묶음 강의:
[Working with Animation Data / A-COM Lesson 2](https://dev.epicgames.com/community/learning/tutorials/6mae/working-with-animation-data-in-unreal-engine-5-6-a-com-animation-sample-lesson-2).
2025-11-05 공개, 2025-12-02 갱신, UE 5.6 기반. 베이크·레이어·커브 편집을 함께 다룬다.
[Epic의 강의 소개](https://www.unrealengine.com/learning/november-epic-learning-content-animation-game-profiling-and-more)에서도 해당 내용과 무료 학습 자료임을 확인했다.

### 2. 현재 엔진 도구와 리그 제작 — 구현 담당 참고

**State of Rigging and Animation Tools in Unreal Engine 5.8 | Unreal Fest Chicago 2026**

- 제작자: Unreal Engine 공식 채널.
- YouTube 공개일: 2026-07-14.
- [영상](https://www.youtube.com/watch?v=yi-oDmC1nqU)
- 주제: UE 5.8의 리깅·애니메이션 도구와 리깅/애니메이션 협업 시연.
- 적용: 현재 엔진에서 사용할 도구를 고르는 자료. 디딤 공격 하나를 완성하는 단계별 강의와는 구분한다.
- [Epic의 공식 소개](https://www.unrealengine.com/learning/julys-epic-learning-content-animation-mobile-game-development-and-more).

**Bringing Zebra to Life: Animating in Unreal Engine 5.8 | Inside Unreal**

- 제작자: Unreal Engine 공식 채널. 2026년 9월 방송 자료.
- [영상](https://www.youtube.com/watch?v=CfhHFFvcRow)
- 제목과 제작자는 oEmbed로 확인했다. 이번 조사에서 전체 챕터·내용을 확보하지 못해 최우선 실습 자료로 확정하지 않는다.

**Workshop | Rigging in Unreal Engine**

- Epic의 워크숍. 공개 페이지에 2025-12-09 공개 / 2026-07-24 갱신으로 표시된다.
- [워크숍](https://dev.epicgames.com/community/learning/talks-and-demos/jZ74/workshop-rigging-in-unreal-engine)
- 프로젝트·슬라이드가 제공된다. 편집용 리그가 없을 때 리그를 만드는 참고 자료다.
- [Biped Spine and Reverse Foot 강의](https://dev.epicgames.com/community/learning/courses/eNm/unreal-engine-control-rig-biped-spine-and-reverse-foot/98Ea/unreal-engine-introduction)는 척추와 발 제어에 관련된 후속 후보다. 과정 전체 내용을 이번에 검토한 것으로 간주하지 않는다.

### 3. 발 미끄러짐·무게감과 신규 동작 제작 — 외부 도구 대안

**Rokoko Mocap | Cleanup and Editing in Cascadeur**

- 제작자: Cascadeur 공식 팀.
- 공식 강의일: 2025-02-20. 길이 14분 29초.
- [영상](https://www.youtube.com/watch?v=Ojbzc3e0pVk) / [강의 설명과 챕터](https://cascadeur.com/tutor/rokokomocap1)
- 관련 구간: 02:34 지지점, 06:39 물리 보정, **08:22 발 미끄러짐 수정**, 09:27 무게에 따른 균형, 11:00 휘두르기 수정.
- 적용 판단: 현재 문제와 직접 연결되는 보정 원리를 다룬다. 시연 동작이 Crunch용 복싱 공격이라는 뜻은 아니다.

**Physics Pipeline | Everything You Need to Know about AutoPhysics in Cascadeur**

- 공식 강의일: 2025-06-04. 길이 25분 54초. 2025.1 이상.
- [영상](https://www.youtube.com/watch?v=QPPIxzbH1o8) / [설명·챕터](https://cascadeur.com/tutor/physicspipeline2025)
- 관련 구간: **01:06 핵심 자세 만들기**, 01:14 참조 영상, 08:49 자세 사이 연결, 14:44 물리, 19:44 이동 궤적, 20:20 회전, 21:15 보상 동작.
- 적용 판단: 맞는 소스 모션이 없을 때 몇 개의 중요한 자세부터 새 동작을 만드는 절차를 참고할 수 있다.

**Get Started in Cascadeur | Your First Animation Guide**

- 공식 강의일: 2026-04-15. 길이 11분 16초. 2026.1 이상.
- [영상](https://www.youtube.com/watch?v=nUADUrQf97c) / [강의 페이지](https://cascadeur.com/tutor/getstarted1)
- 외부 도구를 시험할 경우의 입문 자료다. 현재 Codex 세션에 Cascadeur를 직접 조작할 연결 도구가 확인된 것은 아니다.
- [현재 플랜](https://cascadeur.com/plans)은 Free를 CASC 내보내기 전용으로 설명한다. Unreal에 가져오기 위한 FBX/DAE 내보내기는 유료 플랜 기능으로 안내된다. 무료 도구만으로 동일 경로가 완결된다고 가정하지 않는다.
- [2026.1 공식 변경 소개](https://cascadeur.com/blog/view/cascadeur-2026-1-new-renderer-ue-live-link)에는 Unreal Live Link와 Root Motion 도구가 설명된다. Crunch 리그 호환성과 UE 5.8.3 연결은 별도 시험 전이다.

### 4. 공격 도달 거리 보정 — 모션 품질 확인 다음

**Unreal Engine 5 Motion Warping Guide — Artofficial Entertainment**

- 2026-03-03 공개.
- [영상](https://www.youtube.com/watch?v=2mPymkxKTQQ)
- 관련 챕터: 02:12 초기 설정, **07:12 보정 구간**, 20:19 실행 중 구간 생성, **35:19 흔한 문제**.
- 적용 판단: 좋은 디딤 동작을 작은 거리 변화에 맞추는 단계에 유용하다. 걷지 않는 다리를 걷는 다리로 만들어 주는 기능으로 취급하지 않는다.
- Crunch에서는 보정 거리 상한, 방향 잠금 시점, 플레이어를 계속 추적하지 않는 약속을 별도로 유지해야 한다.

**Souls-like Enemy AI Part 4: Motion Warping — Zero2GameDev**

- 2026-03-25 공개.
- [영상](https://www.youtube.com/watch?v=jAjYFjaYk6E)
- 08:00~11:00은 Root Motion과 Motion Warping 설정.
- 공격 중 도달 위치 보정의 예시다. 실제 DS3 역설계 자료가 아니며 기존 HFSM/Utility/GOAP를 강의의 Behavior Tree로 교체할 이유도 아니다.
- 강의 설명은 비회원용 Mixamo 소스로 `sword and shield power slash`를 지정한다. 우리 왼손 휘두르기와 같은 에셋은 아니다.

## 프로젝트의 실제 에셋 현황 — 이름·종류 확인

2026-10-07 Asset Registry에서 `/Game`의 저장된 에셋 메타데이터를 조회했다.

| 확인된 에셋 | 이번 작업에서의 의미 | 아직 확인하지 않은 것 |
|---|---|---|
| `/Game/FightAnimations_FBX/A_Step_F`, `A_Step_F_L`, `A_Step_F_R` | 달리기 하체를 쓰기 전에 비교해야 할 전투 디딤 후보 | 실제로 어느 발부터 움직이는지, 바닥 접지, 루트 이동, 시작/끝 자세 |
| `/Game/FightAnimations_FBX/A_PunchBody_R_M`, `A_PunchHead_R_M` | 펀치와 몸 전진이 함께 있는지 조사할 후보 | 이름의 M을 근거로 실제 전진량·Root Motion 존재를 확정하지 않음 |
| `/Game/UAF_H2HCombat/Animations/H2HCombo/LeftHand/AS_Hook-L`, `AS_Jab-L`, `AS_Uppercut-L` | 이미 가진 왼손 공격 후보 | Crunch에 옮긴 품질, 디딤 존재, 현재 공격의 대체 가능성 |
| `/Game/UAF_H2HCombat`의 AnimSequence 143개 | 구매 전에 검토할 기존 전투 라이브러리가 있음 | 143개가 모두 공격이거나 모든 기획을 커버한다는 뜻은 아님 |
| `/Game/Characters/Mannequins/Rigs/CR_Mannequin_Body` 등 | 마네킹용 편집·보정 리그가 있음 | Crunch의 큰 손·몸 비율과 추가 뼈에 호환되지 않을 수 있음 |
| `RTG_Kubold_Quinn`, `IK_Kubold`, `IK_Quinn` | 플레이어 쪽 모션 변환 설정이 있음 | Crunch용 IK Rig/Retargeter로 곧바로 사용할 수 있다고 보지 않음 |
| Crunch의 `Orion_Proto_Retarget`는 `Rig` 종류 | 오래된 리타깃용 Rig 에셋 | 편집용 `ControlRigBlueprint`와 다른 종류임 |

저장된 `/Game` 목록에서 **Crunch 전용 ControlRigBlueprint와 Crunch용 IKRigDefinition/IKRetargeter는 찾지 못했다.**
이 결과는 저장되지 않은 임시 객체나 플러그인 내부 기능의 부재까지 증명하지 않는다.

## 무엇이 없으면 어떤 단계가 막히나

| 부족한 것 | 막히는 작업 | 대응 |
|---|---|---|
| 원하는 동작과 가까운 원본 모션 | 간단한 속도/자세 보정만으로 높은 품질을 얻기 어려움 | 기존 라이브러리 후보 확인 → 샘플 검토 → 핵심 자세 제작 또는 외부 모캡/제작 의뢰 |
| Crunch를 편하게 조절할 편집용 리그 | 발·골반·상체를 함께 조절하고 비교하는 작업이 어려워짐 | Crunch 리그 제작·호환성 검증. FK 편집은 보조 경로이며 발 접지까지 자동 해결하지 않음 |
| 외부 모션을 Crunch에 옮길 설정 | 다른 캐릭터의 좋은 모션을 직접 사용할 수 없음 | 소스/Crunch IK Rig와 Retargeter 구성, 발·손·골반/루트 이동 검증 |
| 모션의 실제 루트 이동 데이터 | Root Motion 옵션을 켜도 필요한 전진이 나오지 않을 수 있음 | 원본 이동량 확인, 편집 단계에서 이동 제작, 게임 이동과 중복하지 않도록 설정 |
| 공격 후 원래 자세로 돌아오는 동작 | 공격만 좋아도 끝날 때 끊김 | 회복 클립 확보 또는 끝 자세/연결 구간 제작 |
| 편집 후 게임용 내보내기 기능 | 외부 도구에서 만든 모션을 Unreal에 가져오지 못함 | 도구·플랜·FBX 지원을 처음에 확인 |

많은 경우 게임 로직의 프로토타입까지 막히는 것은 아니다. 그러나 최종 영상에 사용할 모션 품질은
적절한 소스·리그·편집·검수가 필요하다. 충돌 이동, 잘못된 판정 타이밍, 연결 오류는 에셋을 사도 별도로 고쳐야 한다.

외부 모션을 옮기는 기준 자료:
[Epic IK Rig Retargeting](https://dev.epicgames.com/documentation/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine?lang=en-US),
[UE 5.8 Retargeting Operation Stack](https://dev.epicgames.com/documentation/unreal-engine/retargeting-operation-stack-in-unreal-engine-5-8).
특히 골반 이동과 캐릭터 크기에 따른 이동 변환은 발 미끄러짐·전진 거리와 함께 검사한다.

## 외부 에셋 후보 — 아직 구매 추천 확정 아님

1. [Mixamo](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html): Adobe FAQ는 Adobe ID로 무료 이용 가능한 두 발 인간형 캐릭터·애니메이션 서비스라고 설명한다.
   원하는 공격의 후보를 저비용으로 찾는 경로다. Crunch에 옮긴 품질이나 정확한 오른발→왼손 동작의 존재는 이번에 확인하지 않았다.
2. [MoCap Online PUNCH](https://mocaponline.com/products/ue4-punch-pro): Pro 목록에는 잽·훅·어퍼컷 등 145개와 Root Motion / In-Place 제공이 기재돼 있다.
   [실제 모션 목록](https://mocaponline.com/pages/animlist/punch-pro)을 대조했다. `Left_Hook`, `Left_Hook_FT` 등의 이름만으로 원하는 전진 디딤을 보장하지 않는다. Starter/샘플과 제작사 미리보기부터 검토한다.
3. [Melee Walk Locomotion: Animation Sample](https://www.fab.com/listings/2bfc9081-688c-457e-bcc1-8d72f794dc98): 복서 자세의 Root Motion 이동 143개가 안내된다.
   앞뒤·옆 이동, 시작/멈춤/회전의 후보이며 신규 공격 세트를 해결하는 팩으로 분류하지 않는다. [제작사 미리보기](https://www.youtube.com/watch?v=XSY_LOBJ2Do).

선택 전에 볼 것은 에셋 개수보다 **앞에 둔 발, 착지 순서, 골반의 이동, 펀치의 방향, 회복 자세, 실제 이동 데이터**다.
범위를 맞추기 위해 동작을 과하게 늘려야 하는 후보는 사용을 재검토한다.

## 최신 생성 기술을 바로 채택하지 않는 이유

[Epic AnimGen API](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/AnimGen)와
[AnimGen Example](https://www.fab.com/listings/df37eb46-09bf-4604-9307-cdc39c769790)도 확인했다.
모션 데이터베이스를 학습해 캐릭터 제어기를 만드는 실험적 경로다. 공식 학습 설정에는 입력 Database가 필요하다.
정확한 새 복싱 공격 한 개를 자료 없이 즉시 만들어 주는 기능으로 해석하지 않는다.
동명의 2D 영상/스프라이트 생성 서비스와도 구분한다.

## 한 공격에서 시험할 제작 절차

1. 기존 전투 모션 후보를 원래 캐릭터로 재생해 실제 움직임을 확인한다. 발 순서가 맞지 않으면 다음 후보를 본다.
2. 맞는 후보를 Crunch 체형에 옮기고, 발 접촉·손 궤적·골반/루트 이동을 확인한다.
3. 필요하면 편집용 리그를 만들고 준비 / 오른발 착지 / 타격 / 회복의 중요한 자세를 먼저 정한다.
4. 원본을 보존한 별도 수정 레이어에서 자세와 연결을 편집한다.
5. 바닥이 보이는 정면·측면 영상으로 정상 속도를 먼저 본다. 느린 속도는 발 미끄러짐과 급회전 원인 분석에 쓴다.
6. 동작이 받아들여지면 이동·타격 시간을 맞추고 실제 550cm 접촉, 한 타격당 한 번 피해, 벽에 막히는 이동을 검사한다.
7. 이 한 공격이 성공한 뒤, 같은 방식으로 다른 공격을 만들 수 있는지 확인하고 제작 스킬/지침으로 정리한다.

사거리에 닿는 것과 모션이 좋아 보이는 것을 서로 다른 완료 조건으로 둔다.
현재 버전을 이 절차가 성공했다는 근거로 사용하지 않는다.

## 성공 후에 사용할 사용자 지시문 초안

```text
앞서 품질이 확인된 Crunch 모션 제작 절차를 사용해줘.
먼저 기존 에셋에서 맞는 동작을 찾고, 이름 대신 실제 발·골반·손 움직임을 비교해.
없으면 부족한 에셋/리그/연결 동작을 구체적으로 구분하고 확보 또는 제작 방안을 알려줘.
준비·착지·타격·회복 자세를 맞춘 뒤 원본을 보존하며 편집해.
정상 속도 정면·측면 영상과 실제 사거리 검사를 모두 확인한 경우에만 완성이라고 보고해.
내가 정한 느리고 무거운 복서의 리듬과 공격 방향 잠금 규칙을 유지해.
```

이번 조사에서 애니메이션·전투 AI·에디터 플레이 상태는 변경하지 않았다.
