# 전투 모션 에셋 조사 — 2026-09-28

`Battle`(UE 5.8)용 후보. 판매 페이지의 **명시된 구성**을 정리한 것이며, 구매·다운로드·프로젝트 임포트 또는 5.8 실기 검증은 아직 하지 않았다. Fab의 가격과 지원 엔진 버전은 계정·라이선스 등급·시점에 따라 달라지므로 구매 화면에서 다시 확인한다.

## 1. 복싱: 잽·연속 잽·더킹

| 후보 | 비용 | 판매자가 명시한 관련 클립/구성 | Battle에서의 판단 |
| --- | --- | --- | --- |
| [Boxing Collection — animo-mocap](https://www.fab.com/listings/fae425c4-964e-443d-8a3c-474da7c75dd2) | 유료 | 187개. `AA_Boxing_Jab`, `AA_Boxing_Stepping_Jab`, 좌·우 `The_Bob_n_Weave`, 좌·우 `Dodge_Slip`, `Lead_Hook`/`Rear_Hook`, 가드·풋워크·피격. FBX/UE. | **1순위**. 보스의 잽→잽→훅과 플레이어 더킹 모두 개별 클립으로 조합 가능. 단, 완성된 잽→잽→훅 콤보가 있다고 주장하는 것은 아니다. |
| [Punch Pro — MoCap Online](https://www.fab.com/listings/a6c13b4f-dd80-4845-9e3d-48ddff668f3c) | 유료 | 145개. 좌·우 잽/훅, 블록, 닷지, 위브, 피격. UE4 스켈레톤 기반 UE 프로젝트와 FBX, Root Motion/In-Place, UE5 Manny용 IK Retargeter. [3D 미리보기](https://mocaponline.com/pages/animviewer/punch-pro). | **2순위**. 한 팩으로 공격·방어 리액션을 맞추기 좋다. UE5.8 이식과 현재 캐릭터 발 고정은 샘플 테스트 필요. |
| [Boxing Fight Style](https://www.fab.com/listings/049f4820-c28a-405f-912c-2db7624cb02a) | 유료 | 210개. 펀치 100, 콤보 26, 닷지 8, 닷지 후 카운터 22, 피격 32. 양손잡이 스탠스 4종. | 액션 다양성은 크지만 팩 전체의 잽/더킹 구체 클립명과 현재 캐릭터 리타게팅 품질은 구매 전 영상 확인 필요. |
| [Fighting Animset Pro — Kubold](https://www.fab.com/listings/950a94a9-b25d-4bad-a108-ba190ac91387) | 유료 | 230개 이상. 주먹, 방어, 회피, 웅크림 이동, 피격 등. UE4 표준 스켈레톤 FBX. | 모션 캡처 대안. 복싱 전용은 아니어서 원하는 컴팩트한 잽/더킹이 있는지 미리보기 확인. |
| [Boxing Animation Pack — Ailive](https://www.fab.com/listings/02943b05-f6cb-44d6-b73c-bad3d94dc585) | 유료 | UE5 Manny 기반 10개. 왼손/오른손 펀치, 좌·우 훅, `Dudging_with_a_Ducking`, 풋워크 등. | 소규모 빠른 실험용. 잽이라고 명시된 클립은 없고, 더킹 클립은 명시됨. |
| [Mixamo — Adobe](https://www.mixamo.com/) | **무료** (Adobe ID 필요) | 온라인 모션 라이브러리. `boxing`, `jab`, `hook`, `dodge`로 직접 검색. [공식 FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)는 게임 내 상업 사용을 허용. | 무료 실험용. 클립별 품질과 현재 UE 스켈레톤 리타게팅을 직접 확인해야 한다. |

## 2. 소울라이크/검방패

| 후보 | 비용 | 판매자가 명시한 관련 구성 | Battle에서의 판단 |
| --- | --- | --- | --- |
| [Souls Action RPG Soulslike Animations — AnimStudio](https://www.fab.com/listings/778be5f1-cf25-45d0-8f37-7a8b76e5b4bd) | 유료 | 58개. 한손검+방패, 대검 3타, 구르기, 8방향 사이드스텝, 가드·패리·가드브레이크·경직, 8방향 이동. UE4/UE5 마네킹, Root/In-Place. | **소울라이크 동작 구조 연구 1순위**. 공격과 방어가 한 세트여서 전투 루프 설계 참고에 좋다. |
| [Sword & Shield Animset Pro — Kubold](https://www.fab.com/listings/fb5752ea-c1b4-45f0-b067-7b5816a84299) | 유료 | 모캡 130개 이상. 검 공격·콤보, 가드, 피격, 회피, 이동. FBX 포함. | 무게감/자연스러운 이동 후보. 캐릭터 컨트롤러는 포함되지 않는다. |
| [Sword and Shield Animation Pack](https://www.fab.com/listings/ac3b99c6-27d2-450e-98ca-a998f9e83442) | 유료 | 공격 55, 4방향 회피 16, 구르기 16, 이동·피격·가드 다수. UE4/UE5 마네킹 데모. | 플레이어의 검방패 전투 전반을 비교하는 후보. 실제 클립 개수는 판매 페이지의 세부 목록에서 재확인. |
| [Sword And Shield Animation V3 — GameDevHero](https://www.fab.com/listings/84e41c6d-6583-49a0-a153-4b9b23f260c5) | 유료 | 355개. UE5 마네킹, Root/In-Place, FBX. 가드 관련 7, 회피 5, 대시 8, 반응/처형. | 대량 변형이 필요할 때 후보. 숫자보다 1~2개 핵심 공격의 타이밍과 발 고정을 먼저 검증. |
| [Dynamic Sword Shield Animations V2](https://www.fab.com/listings/bca6036c-717f-4d24-9e37-6baee89c4b81) | 유료 | 72개. 공격 24, 가드 2, 이동 32, 회전 8, 피격 6. UE4/UE5 마네킹, 검·방패 메시. | 적/보스 검방패 동작 후보. 회피 구성은 판매 페이지에 명시되지 않음. |
| [Dynamic Sword Shield Animations V3](https://www.fab.com/listings/fc6bb2a2-fa3b-4dde-8011-605fde4dd85a) | 유료 | 38개. 공격 14, 회피 3, 이베이드 1, 이동 16, 피격 등. UE4/UE5 마네킹, 무기 메시. | 짧은 적 캐릭터 실험에 적당. |
| [Game Animation Sample — Epic](https://www.unrealengine.com/blog/game-animation-sample) | **무료** | 500개 이상 고품질 이동·트래버설 모션, 마네킹 호환, 애니메이션 블루프린트. | 소울라이크 이동/전환의 기반 자료. **검방패 공격 팩은 아니다.** |
| [Free Sample Animation Set — VanillaLoop](https://www.fab.com/listings/5b737d10-b4cd-4294-8f6b-757b9088039d) | **무료** | Roll Dodge Dash 팩에서 선별된 샘플과 이동 모션. | 회피 전환 참고용. 검방패 공격은 없음. |

## 선택 및 검증 순서

1. **현재 복싱 보스 유지:** `Boxing Collection` 영상에서 잽의 준비·타격·회수, 좌/우 더킹의 머리 이동과 발 지지를 확인한다. `Punch Pro` 3D 뷰어와 비교한다.
2. 1개 잽과 1개 더킹만 테스트 프로젝트에 가져와 기존 `Battle` 캐릭터에 리타게팅한다. 잽 두 번을 재생해도 회수 자세가 이어지는지, 훅으로 자연스럽게 넘어가는지 확인한다.
3. 판정 설계와 모션을 분리한다. 더킹 시 머리/캡슐 판정, 무적 시간, 이동 거리와 속도는 클립 길이만으로 결정하지 않는다.
4. **검방패 별도 실험:** `Souls Action RPG Soulslike Animations` 또는 Kubold를 먼저 비교한다. 현재 복싱 보스에 검방패 모션을 혼합하는 것은 전투 콘셉트 변경이므로 별도 결정이 필요하다.

## 라이선스/기술 체크

- [Fab Standard License](https://www.fab.com/eula)는 프로젝트 내 수정·사용을 허용하고 에셋 원본의 단독 재배포를 금지한다. 개별 상품의 라이선스 등급과 파일 제공 형식은 구매 시점에 확인한다.
- FBX/UE5 Manny라고 적힌 상품도 **UE 5.8에서 바로 작동한다고 검증된 것은 아니다**. 현재 캐릭터 스켈레톤, 손 위치, 바닥 접지, Root Motion/In-Place, 몽타주 섹션 전환을 실제 에디터에서 확인한다.
- 가격 표시는 실시간 Fab 화면에서 확인한다. 조사 시점의 검색 결과 가격을 확정 가격으로 기록하지 않았다.
