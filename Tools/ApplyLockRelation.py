"""Target-relative movement and screen-constrained two-character composition.

All changes are native Blueprint graph deltas. No runtime Python is required.
"""
import unreal
import json
import PolishSoulsHits as H
import ApplyDS3CameraPolish as A

P,S=H.P,H.S
node,call,get,put=H.node,H.call,H.get,H.put
ids={}


def prepare():
    backup='/Game/BossArena/Backup/BP_Player_Combat_PreLockRelation_20260929'
    if not unreal.EditorAssetLibrary.does_asset_exist(backup):
        assert unreal.EditorAssetLibrary.duplicate_asset(P,backup)
        assert unreal.EditorAssetLibrary.save_asset(backup)
        print('CREATED:',backup)
    H.variable(P,'MoveBasisYaw','real',0)
    result=S.compile_blueprint(P)
    assert result.success,list(result.errors)
    g='Move'
    ids[g]=A.build(P,g,'Target-relative movement basis',[
        get('Target','LockOnTarget'),call('Valid','KismetSystemLibrary','IsValid'),node('Gate','branch'),
        call('PlayerPos','Actor','K2_GetActorLocation'),call('TargetPos','Actor','K2_GetActorLocation'),
        call('Look','KismetMathLibrary','FindLookAtRotation'),call('BreakLook','KismetMathLibrary','BreakRotator'),
        call('Control','Pawn','GetControlRotation'),call('BreakControl','KismetMathLibrary','BreakRotator'),
        put('LockedBasis','MoveBasisYaw'),put('FreeBasis','MoveBasisYaw'),get('Basis','MoveBasisYaw')])
    for ref,ident in ids[g].items():
        d=S.get_node_details(P,g,ident)
        print(ref,'IN',[p.pin_name for p in d.input_pins],'OUT',[p.pin_name for p in d.output_pins])
    return True


def shoulder():
    g='UpdateCameraFraming'
    m=A.build(P,g,'Lock composition lateral separation',[
        call('LockSide','KismetMathLibrary','SelectFloat'),call('HoldSprint','KismetMathLibrary','SelectFloat'),
        call('SideInterp','KismetMathLibrary','FInterpTo'),call('Offset','KismetMathLibrary','MakeVector'),
        node('SetOffset','member_set',member='SocketOffset',**{'class':'SpringArmComponent'})])
    ids[g]=m
    checked_wire(g,m,[
      ('13F2D77449D406887752988CFDDB12DE.ReturnValue','LockSide.bPickA'),
      ('LockSide.ReturnValue','HoldSprint.B'),('55C7D2D04F056E8E877923BD18407899.Y','HoldSprint.A'),
      ('F70A1B414BD93357555809A242385A30.ReturnValue','HoldSprint.bPickA'),
      ('55C7D2D04F056E8E877923BD18407899.Y','SideInterp.Current'),
      ('HoldSprint.ReturnValue','SideInterp.Target'),('2694CB8A4457662E9AF980BE72027D2D.ReturnValue','SideInterp.DeltaTime'),
      ('SideInterp.ReturnValue','Offset.Y'),('Offset.ReturnValue','SetOffset.SocketOffset'),
      ('3054D24348C2C7CB6BABC99AF74A230B.CameraBoom','SetOffset.self'),
      ('1374296A4BD15FBA8A86CDB4E8A67CAB.then','SetOffset.execute'),
      ('SetOffset.then','40D4D182437161F05FF9E6932F839DD3.execute')])
    for ref,pin,value in [('LockSide','A',-55),('LockSide','B',0),('SideInterp','InterpSpeed',6),
                          ('Offset','X',0),('Offset','Z',0)]:
        assert S.set_node_pin_value(P,g,m[ref],pin,str(value))
    A.label(P,g,m,'Two-character framing: lateral slide only; hold offset during sprint; never change arm or FOV')
    r=S.compile_blueprint(P)
    print('COMPILED: shoulder',r.success,r.num_errors,list(r.errors))
    assert r.success,list(r.errors)
    assert unreal.EditorAssetLibrary.save_asset(P)
    print('SAVED:',P)
    with open(unreal.Paths.project_saved_dir()+'VibeUE/lock-relation-node-ids.json','w') as f:json.dump(ids,f,indent=2)
    return True


def horizontal_geometry():
    # Solve yaw against both the player's shoulder position and target screen X.
    # Direct geometry supplies feed-forward during orbit; an error-only loop
    # would lag badly at minimum capsule separation.
    g='UpdateLockOnRotation';old=ids[g]
    m=A.build(P,g,'Two-character horizontal geometry',[
      get('Arm','CameraBoom'),get('Length','CamLockArm'),
      node('Socket','member_get',member='SocketOffset',**{'class':'SpringArmComponent'}),
      call('SocketXYZ','KismetMathLibrary','BreakVector'),
      call('L','KismetMathLibrary','Multiply_DoubleDouble'),
      call('LD','KismetMathLibrary','Multiply_DoubleDouble'),
      call('Numerator','KismetMathLibrary','Add_DoubleDouble'),
      call('LSquared','KismetMathLibrary','Multiply_DoubleDouble'),
      call('OnePlus','KismetMathLibrary','Add_DoubleDouble'),call('Root','KismetMathLibrary','Sqrt'),
      call('Distance','KismetMathLibrary','FMax'),call('Denominator','KismetMathLibrary','Multiply_DoubleDouble'),
      call('Ratio','KismetMathLibrary','Divide_DoubleDouble'),call('SinRange','KismetMathLibrary','FClamp'),
      call('Asin','KismetMathLibrary','DegAsin'),call('Atan','KismetMathLibrary','DegAtan'),
      call('Bias','KismetMathLibrary','Add_DoubleDouble'),call('Angle','KismetMathLibrary','Subtract_DoubleDouble')])
    checked_wire(g,{**old,**m},[
      ('Arm.CameraBoom','Socket.self'),('Socket.SocketOffset','SocketXYZ.InVec'),
      ('HorizontalTan.ReturnValue','L.A'),('L.ReturnValue','LD.A'),('Length.CamLockArm','LD.B'),
      ('LD.ReturnValue','Numerator.A'),('SocketXYZ.Y','Numerator.B'),
      ('L.ReturnValue','LSquared.A'),('L.ReturnValue','LSquared.B'),('LSquared.ReturnValue','OnePlus.A'),
      ('OnePlus.ReturnValue','Root.A'),('068E7DA64463295CCD308984C37414CB.ReturnValue','Distance.A'),
      ('Distance.ReturnValue','Denominator.A'),('Root.ReturnValue','Denominator.B'),
      ('Numerator.ReturnValue','Ratio.A'),('Denominator.ReturnValue','Ratio.B'),
      ('Ratio.ReturnValue','SinRange.Value'),('SinRange.ReturnValue','Asin.A'),('L.ReturnValue','Atan.A'),
      ('Asin.ReturnValue','Bias.A'),('Atan.ReturnValue','Bias.B'),
      ('FC75EDAC4FFECED954598DA6603B9D13.Yaw','Angle.A'),('Bias.ReturnValue','Angle.B'),
      ('Angle.ReturnValue','CacheYaw.FrameDesiredYaw')])
    for ref,pin,value in [('L','B',-.02),('OnePlus','B',1),('Distance','B',180),
                          ('SinRange','Min',-.85),('SinRange','Max',.85)]:
        assert S.set_node_pin_value(P,g,m[ref],pin,str(value))
    A.label(P,g,m,'Analytic yaw: target X=.48 and shoulder=-55cm; track target motion independently of screen feedback')
    ids[g].update(m)
    r=S.compile_blueprint(P)
    print('COMPILED: horizontal geometry',r.success,r.num_errors,list(r.errors),list(r.warnings))
    assert r.success,list(r.errors)
    assert unreal.EditorAssetLibrary.save_asset(P)
    print('SAVED:',P)
    with open(unreal.Paths.project_saved_dir()+'VibeUE/lock-relation-node-ids.json','w') as f:json.dump(ids,f,indent=2)
    return True


def orbit_radius():
    for name,kind,value in [('OrbitRadius','real',0),('OrbitBias','real',0),('bOrbitActive','bool','false')]:
        H.variable(P,name,kind,value)
    r=S.compile_blueprint(P);assert r.success,list(r.errors)
    g='Move';old=ids[g]
    m=A.build(P,g,'Orbit radius steering',[
      call('AbsX','KismetMathLibrary','Abs'),call('AbsY','KismetMathLibrary','Abs'),
      call('HasSide','KismetMathLibrary','Greater_DoubleDouble'),call('NoRadial','KismetMathLibrary','Less_DoubleDouble'),
      call('PureSide','KismetMathLibrary','BooleanAND'),node('OrbitGate','branch'),
      get('Active','bOrbitActive'),get('Last','LastMoveInput'),call('LastXY','KismetMathLibrary','BreakVector2D'),
      call('AbsLastX','KismetMathLibrary','Abs'),call('PreviousSide','KismetMathLibrary','Greater_DoubleDouble'),
      call('Continuing','KismetMathLibrary','BooleanAND'),node('ContinueGate','branch'),
      call('Distance','Actor','GetHorizontalDistanceTo'),put('CaptureRadius','OrbitRadius'),
      put('Activate','bOrbitActive'),put('Deactivate','bOrbitActive'),put('ResetBias','OrbitBias'),
      get('Radius','OrbitRadius'),call('Error','KismetMathLibrary','Subtract_DoubleDouble'),
      call('Gain','KismetMathLibrary','Multiply_DoubleDouble'),call('Limit','KismetMathLibrary','FClamp'),
      put('Bias','OrbitBias'),get('ReadBias','OrbitBias'),call('RadialScale','KismetMathLibrary','Add_DoubleDouble')])
    checked_wire(g,{**old,**m},[
      ('D6F211D44F54F1B0CB4F279E2501A723.X Axis','AbsX.A'),
      ('D6F211D44F54F1B0CB4F279E2501A723.Y Axis','AbsY.A'),
      ('AbsX.ReturnValue','HasSide.A'),('AbsY.ReturnValue','NoRadial.A'),
      ('HasSide.ReturnValue','PureSide.A'),('NoRadial.ReturnValue','PureSide.B'),
      ('PureSide.ReturnValue','OrbitGate.Condition'),('LockedBasis.then','OrbitGate.execute'),
      ('OrbitGate.then','ContinueGate.execute'),('OrbitGate.else','Deactivate.execute'),
      ('FreeBasis.then','Deactivate.execute'),('Deactivate.then','ResetBias.execute'),
      ('ResetBias.then','4F04CB80417221572D8834A26AD30755.execute'),
      ('Last.LastMoveInput','LastXY.InVec'),('LastXY.X','AbsLastX.A'),('AbsLastX.ReturnValue','PreviousSide.A'),
      ('Active.bOrbitActive','Continuing.A'),('PreviousSide.ReturnValue','Continuing.B'),
      ('Continuing.ReturnValue','ContinueGate.Condition'),('ContinueGate.then','Bias.execute'),
      ('ContinueGate.else','CaptureRadius.execute'),('CaptureRadius.then','Activate.execute'),
      ('Activate.then','Bias.execute'),('Target.LockOnTarget','Distance.OtherActor'),
      ('Distance.ReturnValue','CaptureRadius.OrbitRadius'),('Distance.ReturnValue','Error.A'),
      ('Radius.OrbitRadius','Error.B'),('Error.ReturnValue','Gain.A'),('Gain.ReturnValue','Limit.Value'),
      ('Limit.ReturnValue','Bias.OrbitBias'),('Bias.then','4F04CB80417221572D8834A26AD30755.execute'),
      ('D6F211D44F54F1B0CB4F279E2501A723.Y Axis','RadialScale.A'),
      ('ReadBias.OrbitBias','RadialScale.B'),('RadialScale.ReturnValue','41A1E77C4096FFC428A4E2AD2C871937.ScaleValue'),
      ('RadialScale.ReturnValue','BFEC814C44E4FA7E65DE6AB58FB69B74.A')])
    for ref,pin,value in [('HasSide','B',.1),('NoRadial','B',.1),('PreviousSide','B',.1),
      ('Activate','bOrbitActive','true'),('Deactivate','bOrbitActive','false'),('ResetBias','OrbitBias',0),
      ('Gain','B',.02),('Limit','Min',-.25),('Limit','Max',.25)]:
        assert S.set_node_pin_value(P,g,m[ref],pin,str(value))
    A.label(P,g,m,'Pure strafe keeps starting radius with bounded input steering (.02/cm, max .25); no teleport')
    ids[g].update(m)
    r=S.compile_blueprint(P)
    print('COMPILED: orbit steering',r.success,r.num_errors,list(r.errors),list(r.warnings))
    assert r.success,list(r.errors)
    assert unreal.EditorAssetLibrary.save_asset(P)
    print('SAVED:',P)
    with open(unreal.Paths.project_saved_dir()+'VibeUE/lock-relation-node-ids.json','w') as f:json.dump(ids,f,indent=2)
    return True


def movement():
    g='Move';m=ids[g]
    pairs=[('Target.LockOnTarget','Valid.Object'),('Valid.ReturnValue','Gate.Condition'),
      ('Target.LockOnTarget','TargetPos.self'),('PlayerPos.ReturnValue','Look.Start'),
      ('TargetPos.ReturnValue','Look.Target'),('Look.ReturnValue','BreakLook.InRot'),
      ('BreakLook.Yaw','LockedBasis.MoveBasisYaw'),('Control.ReturnValue','BreakControl.InRot'),
      ('BreakControl.Yaw','FreeBasis.MoveBasisYaw'),
      ('D6F211D44F54F1B0CB4F279E2501A723.then','Gate.execute'),
      ('Gate.then','LockedBasis.execute'),('Gate.else','FreeBasis.execute'),
      ('LockedBasis.then','4F04CB80417221572D8834A26AD30755.execute'),
      ('FreeBasis.then','4F04CB80417221572D8834A26AD30755.execute'),
      ('Basis.MoveBasisYaw','EC97C129433A3FD5DE00BB9D966A0B80.InRot_Yaw'),
      ('Basis.MoveBasisYaw','64CEE60A4F20423F96C74DA86805EA3E.InRot_Yaw')]
    checked_wire(g,m,pairs)
    A.label(P,g,m,'Lock movement: W/S radial; A/D tangent; free/sprint uses control yaw')
    result=S.compile_blueprint(P)
    print('COMPILED: movement',result.success,result.num_errors,list(result.errors))
    assert result.success,list(result.errors)
    return True


def checked_wire(g,m,pairs):
    # Discover every generated pin before any wiring; validate the whole batch.
    for src,dst in pairs:
        ar,ap=src.split('.',1);br,bp=dst.split('.',1)
        ad=S.get_node_details(P,g,m.get(ar,ar));bd=S.get_node_details(P,g,m.get(br,br))
        assert ap in {p.pin_name for p in ad.output_pins},('output',src)
        assert bp in {p.pin_name for p in bd.input_pins},('input',dst)
    A.wire(P,g,m,pairs)
    print('MODIFIED:',P,g,len(pairs),'validated connections')


def apply():
    """One-time delta; refuse partial/repeated application rather than duplicate nodes."""
    complete=any(n.node_title.startswith('Pure strafe keeps starting radius')
                 for n in S.get_nodes_in_graph(P,'Move',0,'',False))
    if complete:
        print('ALREADY_APPLIED:',P)
        return True
    assert 'MoveBasisYaw' not in {v.variable_name for v in S.list_variables(P)}, \
        'Partial application exists; inspect before resuming specific steps.'
    prepare();movement();prepare_composition();composition();shoulder();horizontal_geometry();orbit_radius()
    return True


def prepare_composition():
    for name in ['FramePlayerY','FrameBossY','FrameBossX','FrameTopY','FrameBottomY',
                 'FrameDesiredPitch','FrameDesiredYaw']:
        H.variable(P,name,'real',0)
    result=S.compile_blueprint(P)
    assert result.success,list(result.errors)
    g='UpdateLockOnRotation'
    ns=[call('PC','GameplayStatics','GetPlayerController'),
        call('Viewport','PlayerController','GetViewportSize'),call('Height','KismetMathLibrary','Max'),
        call('PlayerPos','Actor','K2_GetActorLocation'),
        node('PlayerCapsule','member_get',member='CapsuleComponent',**{'class':'Character'}),
        node('BossCapsule','member_get',member='CapsuleComponent',**{'class':'Character'}),
        call('PlayerHalf','CapsuleComponent','GetScaledCapsuleHalfHeight'),
        call('BossHalf','CapsuleComponent','GetScaledCapsuleHalfHeight'),
        call('PlayerExtent','KismetMathLibrary','MakeVector'),call('BossExtent','KismetMathLibrary','MakeVector'),
        call('BossCoreHeight','KismetMathLibrary','Multiply_DoubleDouble'),
        call('BossCoreExtent','KismetMathLibrary','MakeVector'),
        call('PlayerHead','KismetMathLibrary','Add_VectorVector'),call('PlayerFeet','KismetMathLibrary','Subtract_VectorVector'),
        call('BossHead','KismetMathLibrary','Add_VectorVector'),call('BossFeet','KismetMathLibrary','Subtract_VectorVector'),
        call('BossCore','KismetMathLibrary','Add_VectorVector')]
    for point in ['PlayerCore','BossCore','PlayerHead','PlayerFeet','BossHead','BossFeet']:
        ns += [call(point+'Project','PlayerController','ProjectWorldLocationToScreen'),
               call(point+'XY','KismetMathLibrary','BreakVector2D'),
               call(point+'Y','KismetMathLibrary','Divide_DoubleDouble')]
    ns += [call('BossX','KismetMathLibrary','Divide_DoubleDouble'),
        call('Top','KismetMathLibrary','FMin'),call('Bottom','KismetMathLibrary','FMax')]
    for ref,name in [('CachePlayer','FramePlayerY'),('CacheBoss','FrameBossY'),('CacheBossX','FrameBossX'),
                     ('CacheTop','FrameTopY'),('CacheBottom','FrameBottomY'),
                     ('CachePitch','FrameDesiredPitch'),('CacheYaw','FrameDesiredYaw')]:ns.append(put(ref,name))
    for ref,name in [('PlayerY','FramePlayerY'),('BossY','FrameBossY'),('TargetX','FrameBossX'),
                     ('TopY','FrameTopY'),('BottomY','FrameBottomY'),
                     ('DesiredPitch','FrameDesiredPitch'),('DesiredYaw','FrameDesiredYaw')]:ns.append(get(ref,name))
    # Screen-space error -> angular correction. Safety edges take precedence.
    ns += [call('PlayerError','KismetMathLibrary','Subtract_DoubleDouble'),
        call('BossError','KismetMathLibrary','Subtract_DoubleDouble'),
        call('PlayerWeight','KismetMathLibrary','Multiply_DoubleDouble'),
        call('BossWeight','KismetMathLibrary','Multiply_DoubleDouble'),
        call('Error','KismetMathLibrary','Add_DoubleDouble'),call('AbsError','KismetMathLibrary','Abs'),
        call('OutsideBand','KismetMathLibrary','Greater_DoubleDouble'),
        call('BandError','KismetMathLibrary','SelectFloat'),
        call('DoubleTan','KismetMathLibrary','Multiply_DoubleDouble'),
        call('ErrorTan','KismetMathLibrary','Multiply_DoubleDouble'),
        call('ErrorAngle','KismetMathLibrary','DegAtan'),
        call('Pitch','KismetMathLibrary','Subtract_DoubleDouble'),
        call('TopError','KismetMathLibrary','Subtract_DoubleDouble'),
        call('BottomError','KismetMathLibrary','Subtract_DoubleDouble'),
        call('TopTan','KismetMathLibrary','Multiply_DoubleDouble'),
        call('BottomTan','KismetMathLibrary','Multiply_DoubleDouble'),
        call('TopAngle','KismetMathLibrary','DegAtan'),call('BottomAngle','KismetMathLibrary','DegAtan'),
        call('PitchMin','KismetMathLibrary','Subtract_DoubleDouble'),
        call('PitchMax','KismetMathLibrary','Subtract_DoubleDouble'),
        call('SafePitch','KismetMathLibrary','FClamp'),
        call('XError','KismetMathLibrary','Subtract_DoubleDouble'),
        call('Aspect','KismetMathLibrary','Divide_DoubleDouble'),
        call('HorizontalTan','KismetMathLibrary','Multiply_DoubleDouble'),
        call('XErrorTan','KismetMathLibrary','Multiply_DoubleDouble'),
        call('XAngle','KismetMathLibrary','DegAtan'),call('XStep','KismetMathLibrary','FClamp'),
        call('Yaw','KismetMathLibrary','Add_DoubleDouble')]
    ids[g]=A.build(P,g,'Two-character screen-space composition',ns)
    for ref in ['PC','Viewport','PlayerCapsule','BossCapsule','PlayerCoreProject','PlayerCoreXY','Height','SafePitch']:
        d=S.get_node_details(P,g,ids[g][ref])
        print('DISCOVERED:',ref,'IN',[p.pin_name for p in d.input_pins],'OUT',[p.pin_name for p in d.output_pins])
    return True


def composition():
    g='UpdateLockOnRotation';m=ids[g]
    boss_pos='7F68B4E34E26A0AC6BDA8A9A9E1CE760.ReturnValue'
    current_pitch='DD49D97E4EAA1F6CFF03D3BD455FDE77.Pitch'
    current_yaw='DD49D97E4EAA1F6CFF03D3BD455FDE77.Yaw'
    # Character cast has already succeeded on this execution path.
    char_out=A.cast_out(P,g,'4BDB35AD4D30F912F40C9CB13A1193D2')
    pairs=[('PC.ReturnValue','Viewport.self'),('Viewport.SizeY','Height.A'),
      ('C1ADA9DD42B0640811D92CA24F9662FC.self','PlayerCapsule.self'),
      ('PlayerCapsule.CapsuleComponent','PlayerHalf.self'),
      ('4BDB35AD4D30F912F40C9CB13A1193D2.'+char_out,'BossCapsule.self'),
      ('BossCapsule.CapsuleComponent','BossHalf.self'),('PlayerHalf.ReturnValue','PlayerExtent.Z'),
      ('BossHalf.ReturnValue','BossExtent.Z'),('BossHalf.ReturnValue','BossCoreHeight.A'),
      ('BossCoreHeight.ReturnValue','BossCoreExtent.Z'),
      ('PlayerPos.ReturnValue','PlayerHead.A'),('PlayerExtent.ReturnValue','PlayerHead.B'),
      ('PlayerPos.ReturnValue','PlayerFeet.A'),('PlayerExtent.ReturnValue','PlayerFeet.B'),
      (boss_pos,'BossHead.A'),('BossExtent.ReturnValue','BossHead.B'),
      (boss_pos,'BossFeet.A'),('BossExtent.ReturnValue','BossFeet.B'),
      (boss_pos,'BossCore.A'),('BossCoreExtent.ReturnValue','BossCore.B')]
    for ref,source in [('PlayerCore','PlayerPos'),('BossCore','BossCore'),('PlayerHead','PlayerHead'),
                       ('PlayerFeet','PlayerFeet'),('BossHead','BossHead'),('BossFeet','BossFeet')]:
        pairs += [('PC.ReturnValue',ref+'Project.self'),(source+'.ReturnValue',ref+'Project.WorldLocation'),
                  (ref+'Project.ScreenLocation',ref+'XY.InVec'),(ref+'XY.Y',ref+'Y.A'),
                  ('Height.ReturnValue',ref+'Y.B')]
    pairs += [('BossCoreXY.X','BossX.A'),('Viewport.SizeX','BossX.B'),
      ('PlayerHeadY.ReturnValue','Top.A'),('BossHeadY.ReturnValue','Top.B'),
      ('PlayerFeetY.ReturnValue','Bottom.A'),('BossFeetY.ReturnValue','Bottom.B'),
      ('PlayerCoreY.ReturnValue','CachePlayer.FramePlayerY'),('BossCoreY.ReturnValue','CacheBoss.FrameBossY'),
      ('BossX.ReturnValue','CacheBossX.FrameBossX'),('Top.ReturnValue','CacheTop.FrameTopY'),
      ('Bottom.ReturnValue','CacheBottom.FrameBottomY'),
      ('93FA2CC34693EF5FF156159A2824F8DB.then','CachePlayer.execute'),
      ('CachePlayer.then','CacheBoss.execute'),('CacheBoss.then','CacheBossX.execute'),
      ('CacheBossX.then','CacheTop.execute'),('CacheTop.then','CacheBottom.execute'),
      ('CacheBottom.then','CachePitch.execute'),('CachePitch.then','CacheYaw.execute'),
      ('CacheYaw.then','2863F7D14E733373E8B01B84663A3693.execute'),
      ('PlayerY.FramePlayerY','PlayerError.A'),('BossY.FrameBossY','BossError.A'),
      ('PlayerError.ReturnValue','PlayerWeight.A'),('BossError.ReturnValue','BossWeight.A'),
      ('PlayerWeight.ReturnValue','Error.A'),('BossWeight.ReturnValue','Error.B'),
      ('Error.ReturnValue','AbsError.A'),('AbsError.ReturnValue','OutsideBand.A'),
      ('Error.ReturnValue','BandError.A'),('OutsideBand.ReturnValue','BandError.bPickA'),
      ('7FDCC8614E34BBD651306CB604E0FAE6.ReturnValue','DoubleTan.A'),
      ('DoubleTan.ReturnValue','ErrorTan.B'),('BandError.ReturnValue','ErrorTan.A'),
      ('ErrorTan.ReturnValue','ErrorAngle.A'),(current_pitch,'Pitch.A'),('ErrorAngle.ReturnValue','Pitch.B'),
      ('TopY.FrameTopY','TopError.A'),('BottomY.FrameBottomY','BottomError.A'),
      ('TopError.ReturnValue','TopTan.A'),('BottomError.ReturnValue','BottomTan.A'),
      ('DoubleTan.ReturnValue','TopTan.B'),('DoubleTan.ReturnValue','BottomTan.B'),
      ('TopTan.ReturnValue','TopAngle.A'),('BottomTan.ReturnValue','BottomAngle.A'),
      (current_pitch,'PitchMin.A'),('TopAngle.ReturnValue','PitchMin.B'),
      (current_pitch,'PitchMax.A'),('BottomAngle.ReturnValue','PitchMax.B'),
      ('Pitch.ReturnValue','SafePitch.Value'),('PitchMin.ReturnValue','SafePitch.Min'),
      ('PitchMax.ReturnValue','SafePitch.Max'),('SafePitch.ReturnValue','CachePitch.FrameDesiredPitch'),
      ('DesiredPitch.FrameDesiredPitch','227300A744C56B907B8F8883F362FDF3.Value'),
      ('TargetX.FrameBossX','XError.A'),('Viewport.SizeX','Aspect.A'),('Height.ReturnValue','Aspect.B'),
      ('DoubleTan.ReturnValue','HorizontalTan.A'),('Aspect.ReturnValue','HorizontalTan.B'),
      ('XError.ReturnValue','XErrorTan.A'),('HorizontalTan.ReturnValue','XErrorTan.B'),
      ('XErrorTan.ReturnValue','XAngle.A'),('XAngle.ReturnValue','XStep.Value'),
      (current_yaw,'Yaw.A'),('XStep.ReturnValue','Yaw.B'),('Yaw.ReturnValue','CacheYaw.FrameDesiredYaw'),
      ('DesiredYaw.FrameDesiredYaw','E1043B3545A02EE6DE1306B365F03362.Yaw')]
    checked_wire(g,m,pairs)
    values=[('Height','B',1),('BossCoreHeight','B',.45),('PlayerError','B',.70),('BossError','B',.36),
      ('PlayerWeight','B',.35),('BossWeight','B',.65),('OutsideBand','B',.012),('BandError','B',0),
      ('DoubleTan','B',2),('TopError','B',.075),('BottomError','B',.93),
      ('XError','B',.48),('XStep','Min',-6),('XStep','Max',6)]
    for ref,pin,value in values:assert S.set_node_pin_value(P,g,m[ref],pin,str(value)),(ref,pin)
    for ref in ['PlayerCore','BossCore','PlayerHead','PlayerFeet','BossHead','BossFeet']:
        assert S.set_node_pin_value(P,g,m[ref+'Project'],'bPlayerViewportRelative','true')
    A.label(P,g,m,'Lock composition: stable body points -> viewport -> two-person goals + head/feet safety, fixed lens')
    result=S.compile_blueprint(P)
    print('COMPILED: composition',result.success,result.num_errors,list(result.errors),list(result.warnings))
    assert result.success,list(result.errors)
    return True
