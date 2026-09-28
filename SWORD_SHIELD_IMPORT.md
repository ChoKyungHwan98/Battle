# Sword & Shield Animset Pro 설치 결과

설치일: 2026-09-28 · Unreal Engine 5.8.3

## 설치 위치

콘텐츠 브라우저: `/Game/ThirdParty/Kubold/SwordShieldAnimsetPro`

원본: `C:/Users/Admin/Downloads/Sword and Shield Animset Pro v1.18.unitypackage`

추출 원본: `C:/Users/Admin/Downloads/SwordShieldAnimsetPro_v1_18_UnrealSource`

| 폴더 | 설치된 내용 |
| --- | --- |
| `Animations/Part1` | 64개: 이동, 대기, 장비, 회피, 피격, 가드 등 |
| `Animations/Part2` | 45개: 공격 연계, 특수 공격, 카운터 등 |
| `Animations/Part3` | 9개: 낙하, 착지, 무기 자세/시선 보조 동작 |
| `Animations/Part4` | 6개: 등반, 플랫폼 점프/착지 |
| `Animations/Part5` | 9개: 대각 방향 이동 |
| `Models` | 원본 Dummy 캐릭터, HumanIK Skeleton, 검·방패 Static Mesh |
| `Textures` | 캐릭터 1개, 검·방패 각각 Diffuse/Normal/Specular 3개: 총 7개 |
| `Materials` | 캐릭터·검·방패용 Unreal 재질 3개 |

총 147개 에셋. 애니메이션은 **133개 = 동작 128개 + 각 FBX의 Bindpose 5개**다.

## 검증 결과

- 모든 애니메이션을 에디터 API로 다시 읽어 30fps, 뼈대 트랙 74개, 양의 재생 길이를 확인하고 저장했다.
- 원본 Unity 설정의 반복 동작 23개에 `loop` 설정을 반영했다.
- 재질 3개의 컴파일 오류가 없고, 메시별 재질 연결을 다시 읽어 확인했다.
- 원본 캐릭터의 `Sword_Idle` 0.5초 및 `Sword_Attack_R` 0.4초 포즈 이미지를 생성·검토했다.
- 신규 에셋만 해당 폴더에 저장했다. 현재 플레이어/보스 그래프와 조작키를 변경하지 않았다.

검증 보고서: `Saved/CodexImports/SwordShieldAnimsetPro_v1_18_verification.json`

임포트 목록: `Saved/CodexImports/SwordShieldAnimsetPro_v1_18.json`

포즈 이미지: `Saved/CodexImports/SwordShieldPreview/Sword_Idle.png`, `Sword_Attack_R.png`

## 다음 적용 단계

현재 설치물은 **원본 HumanIK 스켈레톤용 모션 라이브러리**다. 현재 Quinn/Manny 플레이어에 직접 재생할 수 있는 형태로 리타게팅한 것은 아니다.

플레이어에 적용하려면 IK Rig/Retargeter를 만들고, 대기·기본 공격·회피를 먼저 변환해 발 고정, 손목 방향, 무기 소켓을 확인한다. 이후 필요한 모션만 몽타주와 현재 전투 시스템에 연결한다.

Unity의 PlayMaker 컨트롤러·AI·입력 설정·프리팹은 Unreal 시스템으로 변환하지 않았다. `_Add` 이름의 보조 동작도 원본 절대 포즈로 가져왔으며, 사용 시 Unreal의 additive 기준 포즈 설정이 필요하다. Root Motion 추출은 자동으로 활성화하지 않았다.

재질은 원본 텍스처를 Unreal Base Color/Normal/Specular로 연결하고 roughness를 지정한 기본 변환이다. Unity 셰이더와 화면이 완전히 같다는 검증은 하지 않았다. 노멀 맵의 녹색 채널은 Unreal 방향으로 뒤집었다.

## 임포트 중 해결한 문제

- 자동 샘플레이트가 1,920fps까지 증가하므로 원본에 맞게 30fps를 명시했다.
- 일부 FBX take 끝 시간이 서브프레임에 있어 임포트가 거부됐다. `snap_to_closest_frame_boundary=True`로 가장 가까운 프레임 경계에 맞췄다.
- FBX 묶음에는 이미 개별 animation take가 들어 있다. 별도의 전체 파일 자르기는 필요하지 않았다.
- 멀티 take 임포트의 `task.imported_object_paths`에는 마지막 클립만 반환될 수 있다. 실제 전체 목록은 명시된 Unity take 목록과 Asset Registry로 검증했다.
- UE 5.8에서 `AnimSequence.data_model`이 `None`일 수 있다. 검증에는 `AnimSequenceService.get_anim_sequence_info`를 사용했다.

`Tools/ImportSwordShieldUnity.py`는 설치된 스켈레톤을 기준으로 FBX 묶음·무기 임포트를 재개하는 도구다. 에디터 MCP Python에서 실행하며, 일반 실행은 기존 에셋을 덮어쓰지 않는다. `repair_failed_phase=True`는 이번 작업에서 생성한 실패 묶음을 복구할 때만 사용했다.

Workflow run: `20260928T080301Z-B1D74C99`
