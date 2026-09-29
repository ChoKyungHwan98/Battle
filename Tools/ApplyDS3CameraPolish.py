"""Camera-only delta edits through Unreal MCP; preserve combat graphs.

Rows 0 and 5110 are read from the local DS3 regulation. Row 5110 is selected
as the Gundyr model profile; its event assignment is not yet extracted.
UE interpolation, screen eligibility and marker rendering are reconstructions.
"""
import unreal
import PolishSoulsHits as H

P, S = H.P, H.S
HUD = '/Game/BossArena/UI/WBP_PlayerHUD'
node, call, get, put = H.node, H.call, H.get, H.put


def build(path, graph, label, nodes, wires=(), defaults=()):
    if any(n.node_title == label for n in S.get_nodes_in_graph(path, graph, 0, '', False)):
        raise RuntimeError('Already applied: ' + label)
    r = S.build_graph(path, graph, nodes,
        [{'from_': a, 'to': b} for a, b in wires],
        [{'node_ref': n, 'pin_name': p, 'value': str(v)} for n, p, v in defaults], False, False)
    ids = dict(r.ref_to_node_id)
    print('ADDED:', path, graph, label, ids)
    assert r.success, list(r.errors)
    return ids


def wire(path, graph, ids, pairs):
    for a, b in pairs:
        ar, ap = a.split('.', 1); br, bp = b.split('.', 1)
        assert S.connect_nodes(path, graph, ids.get(ar, ar), ap, ids.get(br, br), bp), (a,b)


def cast_out(path, graph, ident):
    d = S.get_node_details(path, graph, ident)
    return next(p.pin_name for p in d.output_pins if p.pin_category == 'object')


def label(path, graph, ids, title):
    S.auto_layout_selected_nodes(path, graph, list(ids.values()))
    S.add_comment_around_nodes(path, graph, title, list(ids.values()))


def profile():
    for name, value in [('CamFreeArm',400),('CamLockArm',550),
        ('CamCloseMaxExtra',0),('CamVerticalFOV',43),('CamLockShiftRatio',.2),
        ('CamFreeOffsetZ',52),('CamLockOffsetZ',92),('CamLockPitchMin',-25),
        ('CamLockRange',1500),('CamLockReleaseRange',1500)]:
        assert S.set_variable_default_value(P,name,str(value)),name
        print('MODIFIED:', P, name, value)
    H.variable(P,'LockAimPoint','vector','(X=0,Y=0,Z=0)')
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(P))
    g='UpdateCameraFraming'
    # Bypass the previous ad-hoc near-distance zoom, retaining it for rollback.
    wire(P,g,{},[('303B2DCF477593656A206B91AFC32B36.CamLockArm',
                  'AAB11BA9447FB21F459413AC053B419D.A')])
    title='DS3 camera profile: world pivot 142/182cm, preserve profile during sprint'
    ids=build(P,g,title,[
        node('Pivot','member_get',member='TargetOffset',**{'class':'SpringArmComponent'}),
        call('BreakPivot','KismetMathLibrary','BreakVector'),
        call('HoldPivot','KismetMathLibrary','SelectFloat'),
        node('SetPivot','member_set',member='TargetOffset',**{'class':'SpringArmComponent'})])
    wire(P,g,ids,[
        ('3054D24348C2C7CB6BABC99AF74A230B.CameraBoom','Pivot.self'),
        ('Pivot.TargetOffset','BreakPivot.InVec'),('BreakPivot.Z','HoldPivot.A'),
        ('DA7B7AE048A687AB2DAE32B6DF3CB71A.ReturnValue','HoldPivot.B'),
        ('F70A1B414BD93357555809A242385A30.ReturnValue','HoldPivot.bPickA'),
        ('HoldPivot.ReturnValue','B84EAB894F547D50B72B6CBD137211B9.Target'),
        ('BreakPivot.Z','B84EAB894F547D50B72B6CBD137211B9.Current'),
        ('3054D24348C2C7CB6BABC99AF74A230B.CameraBoom','SetPivot.self'),
        ('0C274C5149731325B6DC43A2C7FB5425.ReturnValue','SetPivot.TargetOffset'),
        ('DEBC65EC447C5801758E8E82E6FCB0C1.then','SetPivot.execute'),
        ('SetPivot.then','40D4D182437161F05FF9E6932F839DD3.execute')])
    S.configure_node(P,g,'F50C536443BDD407260B959A5F5E03FE','NodeComment',
        'Previous Battle near-distance zoom: disconnected, preserved for rollback')
    label(P,g,ids,title)


def aim_point():
    g='UpdateLockOnRotation';title='Lock camera and marker share animated torso point'
    ids=build(P,g,title,[node('TargetCharacter','cast',target_class='/Script/Engine.Character'),
        node('Mesh','member_get',member='Mesh',**{'class':'Character'}),
        call('Torso','SceneComponent','GetSocketLocation'),put('AimPoint','LockAimPoint')],
        defaults=[('Torso','InSocketName','spine_03')])
    out=cast_out(P,g,ids['TargetCharacter'])
    wire(P,g,ids,[('C848B407480BD59463809BA4113FC526.then','TargetCharacter.execute'),
        ('EF2A80F947660F6D15FE629EA3763AAC.LockOnTarget','TargetCharacter.Object'),
        (f'TargetCharacter.{out}','Mesh.self'),('Mesh.Mesh','Torso.self'),
        ('Torso.ReturnValue','AimPoint.LockAimPoint'),('TargetCharacter.then','AimPoint.execute'),
        ('AimPoint.then','63CC4B814192D2F14FBF9193279D2BCD.execute'),
        ('AimPoint.Output_Get','FC8E11D24A431E00CC469899305E891C.Target'),
        ('TargetCharacter.CastFailed','04B8667440927FD78F1085BDF82D5F65.execute')])
    label(P,g,ids,title)


def marker(existing_ids=None):
    W=unreal.WidgetService
    backup='/Game/BossArena/Backup/WBP_PlayerHUD_PreLockMark_20260929'
    if not unreal.EditorAssetLibrary.does_asset_exist(backup):
        assert unreal.EditorAssetLibrary.duplicate_asset(HUD,backup)
        unreal.EditorAssetLibrary.save_asset(backup)
        print('CREATED:',backup)
    if not W.widget_exists(HUD,'LockOnMark'):
        assert W.add_component(HUD,'TextBlock','LockOnMark','RootCanvas',True).success
        print('ADDED:',HUD,'LockOnMark')
    # Font glyph rather than a copied DS3 UI asset. A small white point + dark outline.
    for prop,value in [('Text','●'),('Font.Size','14'),('Font.OutlineSettings.OutlineSize','1'),
        ('ColorAndOpacity','(SpecifiedColor=(R=1,G=1,B=1,A=1))'),
        ('ShadowColorAndOpacity','(R=0,G=0,B=0,A=.9)'),('ShadowOffset','(X=1,Y=1)'),
        ('Visibility','Collapsed'),('Position X','0'),('Position Y','0'),
        ('Size X','24'),('Size Y','24'),('Alignment X','.5'),('Alignment Y','.5'),('ZOrder','10')]:
        assert W.set_property(HUD,'LockOnMark',prop,value),prop
        print('MODIFIED:',HUD,'LockOnMark',prop,W.get_property(HUD,'LockOnMark',prop))
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(HUD))
    g='EventGraph';title='Lock marker: project torso to DPI-correct HUD, hide on unlock/sprint'
    descriptions=[
        node('Target','member_get',member='LockOnTarget',**{'class':P+'.BP_Player_Combat_C'}),
        node('AimPoint','member_get',member='LockAimPoint',**{'class':P+'.BP_Player_Combat_C'}),
        call('Valid','KismetSystemLibrary','IsValid'),node('Gate','branch'),
        call('PC','UserWidget','GetOwningPlayer'),
        call('Project','WidgetLayoutLibrary','ProjectWorldLocationToWidgetPosition'),
        node('Projected','branch'),get('Mark','LockOnMark'),
        call('Slot','WidgetLayoutLibrary','SlotAsCanvasSlot'),
        call('Position','CanvasPanelSlot','SetPosition'),
        call('Show','Widget','SetVisibility'),call('Hide','Widget','SetVisibility')]
    if existing_ids:
        ids=dict(existing_ids)
        ids.update(build(HUD,g,title,descriptions[:2]))
    else:
        ids=build(HUD,g,title,descriptions,defaults=[('Project','bPlayerViewportRelative','true'),
                  ('Show','InVisibility','HitTestInvisible'),('Hide','InVisibility','Collapsed')])
    playerpin=cast_out(HUD,g,'5A8219204C09350BD61203801D9BB0F6')
    wire(HUD,g,ids,[
        ('50F511A343552C7C81F31E855E38B051.then','Gate.execute'),
        (f'5A8219204C09350BD61203801D9BB0F6.{playerpin}','Target.self'),
        (f'5A8219204C09350BD61203801D9BB0F6.{playerpin}','AimPoint.self'),
        ('Target.LockOnTarget','Valid.Object'),('Valid.ReturnValue','Gate.Condition'),
        ('Gate.then','Projected.execute'),('PC.ReturnValue','Project.PlayerController'),
        ('AimPoint.LockAimPoint','Project.WorldLocation'),
        ('Project.ReturnValue','Projected.Condition'),
        ('Projected.then','Position.execute'),('Project.ScreenPosition','Position.InPosition'),
        ('Mark.LockOnMark','Slot.Widget'),('Slot.ReturnValue','Position.self'),
        ('Position.then','Show.execute'),('Mark.LockOnMark','Show.self'),
        ('Gate.else','Hide.execute'),('Projected.else','Hide.execute'),('Mark.LockOnMark','Hide.self')])
    label(HUD,g,ids,title)


def reset_and_eligibility():
    g='ToggleLockOn';title='Lock/reset: visible living target in range, otherwise face camera behind player'
    # Eligibility is reconstructed from the original game's observable rules.
    ids=build(P,g,title,[
        call('PC','GameplayStatics','GetPlayerController'),
        call('LOS','Controller','LineOfSightTo'),
        node('Alive','member_get',member='CurrentHealth',**{'class':H.B+'.BP_Boss_Crunch_C'}),
        call('Living','KismetMathLibrary','Greater_DoubleDouble'),
        call('TargetLocation','Actor','K2_GetActorLocation'),
        call('Camera','GameplayStatics','GetPlayerCameraManager'),
        call('CameraLocation','PlayerCameraManager','GetCameraLocation'),
        call('CameraRotation','PlayerCameraManager','GetCameraRotation'),
        call('Forward','KismetMathLibrary','GetForwardVector'),
        call('Direction','KismetMathLibrary','GetDirectionUnitVector'),
        call('Dot','KismetMathLibrary','Dot_VectorVector'),
        call('InFront','KismetMathLibrary','Greater_DoubleDouble'),
        call('VisibleAlive','KismetMathLibrary','BooleanAND'),
        call('Eligible','KismetMathLibrary','BooleanAND'),node('Gate','branch'),
        call('BodyRotation','Actor','K2_GetActorRotation'),
        call('BodyBreak','KismetMathLibrary','BreakRotator'),
        call('Control','Pawn','GetControlRotation'),call('ControlBreak','KismetMathLibrary','BreakRotator'),
        call('ResetRotation','KismetMathLibrary','MakeRotator'),
        call('Reset','Controller','SetControlRotation')],
        defaults=[('Living','B',0),('InFront','B',0),('ResetRotation','Roll',0)])
    wire(P,g,ids,[
        ('7428FC854D19F087B4A0F5A049933D2A.then','Gate.execute'),
        ('B1FF5E9E47D1A8E811577ABAB6DFA317.ReturnValue','LOS.Other'),
        ('PC.ReturnValue','LOS.self'),
        ('B1FF5E9E47D1A8E811577ABAB6DFA317.ReturnValue','Alive.self'),
        ('Alive.CurrentHealth','Living.A'),
        ('B1FF5E9E47D1A8E811577ABAB6DFA317.ReturnValue','TargetLocation.self'),
        ('Camera.ReturnValue','CameraLocation.self'),('Camera.ReturnValue','CameraRotation.self'),
        ('CameraLocation.ReturnValue','Direction.From'),('TargetLocation.ReturnValue','Direction.To'),
        ('CameraRotation.ReturnValue','Forward.InRot'),('Forward.ReturnValue','Dot.A'),
        ('Direction.ReturnValue','Dot.B'),('Dot.ReturnValue','InFront.A'),
        ('LOS.ReturnValue','VisibleAlive.A'),('Living.ReturnValue','VisibleAlive.B'),
        ('VisibleAlive.ReturnValue','Eligible.A'),('InFront.ReturnValue','Eligible.B'),
        ('Eligible.ReturnValue','Gate.Condition'),('Gate.then','7F4851234DF768A718360E8AA09EE959.execute'),
        ('A4AF873A46A55C669D6B4F9A15EB8695.else','Reset.execute'),
        ('7428FC854D19F087B4A0F5A049933D2A.else','Reset.execute'),('Gate.else','Reset.execute'),
        ('BodyRotation.ReturnValue','BodyBreak.InRot'),('BodyBreak.Yaw','ResetRotation.Yaw'),
        ('Control.ReturnValue','ControlBreak.InRot'),('ControlBreak.Pitch','ResetRotation.Pitch'),
        ('ResetRotation.ReturnValue','Reset.NewRotation'),('PC.ReturnValue','Reset.self')])
    label(P,g,ids,title)


def target_lifecycle(existing_retention=None):
    g='UpdateLockOnRotation';title='Lock retention: release defeated or out-of-range boss'
    aim_setter=next(n.node_id for n in S.get_nodes_in_graph(P,g,0,'',False)
        if n.node_type=='K2Node_VariableSet' and any(
            p.pin_name=='LockAimPoint' for p in S.get_node_details(P,g,n.node_id).input_pins))
    descriptions=[node('Boss','cast',target_class=H.B),
        node('Health','member_get',member='CurrentHealth',**{'class':H.B+'.BP_Boss_Crunch_C'}),
        call('Living','KismetMathLibrary','Greater_DoubleDouble'),
        call('Retain','KismetMathLibrary','BooleanAND')]
    if existing_retention:
        ids=dict(existing_retention);ids.update(build(P,g,title,descriptions[:1]))
    else:ids=build(P,g,title,descriptions,defaults=[('Living','B',0)])
    out=cast_out(P,g,ids['Boss'])
    wire(P,g,ids,[('EF2A80F947660F6D15FE629EA3763AAC.LockOnTarget','Boss.Object'),
        (f'Boss.{out}','Health.self'),
        (aim_setter+'.then','Boss.execute'),
        ('Boss.then','63CC4B814192D2F14FBF9193279D2BCD.execute'),
        ('Boss.CastFailed','04B8667440927FD78F1085BDF82D5F65.execute'),
        ('Health.CurrentHealth','Living.A'),('Living.ReturnValue','Retain.A'),
        ('71070F304EE56D7F9FC797B23A8BF4BB.ReturnValue','Retain.B'),
        ('Retain.ReturnValue','63CC4B814192D2F14FBF9193279D2BCD.Condition')])
    label(P,g,ids,title)
    g='SetSprinting';title='Sprint restoration: discard defeated or out-of-range saved target'
    ids=build(P,g,title,[node('Boss','cast',target_class=H.B),
        node('Health','member_get',member='CurrentHealth',**{'class':H.B+'.BP_Boss_Crunch_C'}),
        call('Living','KismetMathLibrary','Greater_DoubleDouble'),
        call('Distance','Actor','GetHorizontalDistanceTo'),get('Range','CamLockReleaseRange'),
        call('InRange','KismetMathLibrary','LessEqual_DoubleDouble'),
        call('Restore','KismetMathLibrary','BooleanAND'),node('Gate','branch')],
        defaults=[('Living','B',0)])
    out=cast_out(P,g,ids['Boss'])
    wire(P,g,ids,[('EB1E168C4744918F72D2E0AA64F12BE9.then','Boss.execute'),
        ('03DB11FA45573277015DCBB39814350A.SprintResumeLockTarget','Boss.Object'),
        (f'Boss.{out}','Health.self'),('Boss.then','Gate.execute'),
        ('Boss.CastFailed','2C733998469A47009925CE93E36190BA.execute'),
        ('03DB11FA45573277015DCBB39814350A.SprintResumeLockTarget','Distance.OtherActor'),
        ('Health.CurrentHealth','Living.A'),('Living.ReturnValue','Restore.A'),
        ('Distance.ReturnValue','InRange.A'),('Range.CamLockReleaseRange','InRange.B'),
        ('InRange.ReturnValue','Restore.B'),('Restore.ReturnValue','Gate.Condition'),
        ('Gate.then','67C409834FE8F19C44CF658C600FF9C0.execute'),
        ('Gate.else','2C733998469A47009925CE93E36190BA.execute')])
    label(P,g,ids,title)


def apply():
    profile()
    aim_point()
    marker()
    reset_and_eligibility()
    target_lifecycle()
    for path in [P,HUD]:
        r=S.compile_blueprint(path)
        print('COMPILED:',path,r.success,r.num_errors,list(r.errors))
        assert r.success and r.num_errors==0
        assert unreal.EditorAssetLibrary.save_asset(path)
        print('SAVED:',path)
