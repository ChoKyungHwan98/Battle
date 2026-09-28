"""Apply DS3 camera reference and phase-based controls through Unreal MCP.

Camera numbers come from selected local LOCK_CAM_PARAM_ST rows. Attack times,
root travel and turn rate are Battle/Kubold adaptations, not original DS3 TAE.
"""
import unreal
import PolishSoulsHits as H

P, S = H.P, H.S
node, call, get, put, block = H.node, H.call, H.get, H.put, H.block


def setup():
    for name, kind, value in [
            ('CamVerticalFOV', 'real', 43), ('CamLockShiftRatio', 'real', .40),
            ('CamLockRange', 'real', 1500), ('CamLockReleaseRange', 'real', 2000), ('CamLockPitchMin', 'real', -40),
            ('CamLockPitchMax', 'real', 25), ('AttackStartTime', 'real', 0),
            ('CurrentAttackDuration', 'real', 1), ('AttackTrackingRatio', 'real', .10),
            ('AttackTurnRate', 'real', 360), ('AttackRollCancelRatio', 'real', .60),
            ('bAttackRollWindowOpen', 'bool', 'false'), ('QueuedActionExpires', 'real', 0),
            ('ActionQueueLifetime', 'real', .85), ('bGuardRequested', 'bool', 'false')]:
        H.variable(P, name, kind, value)
    for name, value in [('CamFreeArm',400), ('CamLockArm',600),
                        ('CamFreeOffsetZ',0), ('CamLockOffsetZ',0)]:
        assert S.set_variable_default_value(P,name,str(value))
    for name in ['CamVerticalFOV','CamLockRange','CamLockReleaseRange','CamFreeArm','CamLockArm',
                 'CamLockShiftRatio','AttackTrackingRatio','AttackTurnRate','ActionQueueLifetime']:
        assert S.set_variable_instance_editable(P,name,True)
    for component, values in [
        ('CameraBoom', {'TargetArmLength':'400','RelativeLocation':'(X=0,Y=0,Z=0)',
                        'SocketOffset':'(X=0,Y=0,Z=0)', 'TargetOffset':'(X=0,Y=0,Z=52)',
                        'bEnableCameraLag':'true','CameraLagSpeed':'10',
                        'CameraLagMaxDistance':'60','bUseCameraLagSubstepping':'true',
                        'bEnableCameraRotationLag':'false'}),
        ('FollowCamera', {'FieldOfView':'70.020052',
                          'bOverrideAspectRatioAxisConstraint':'true',
                          'AspectRatioAxisConstraint':'AspectRatio_MaintainXFOV'})]:
        for prop,value in values.items():
            assert S.set_component_property(P,component,prop,value),(component,prop)
            print('MODIFIED:',P,component,prop,value)
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(P))


def camera():
    block(P,'UpdateCameraFraming','DS3 camera: vertical FOV stays 43 degrees across viewport ratios',
        [get('Camera','FollowCamera'),call('PC','Pawn','GetController'),
         node('CastPC','cast',target_class='/Script/Engine.PlayerController'),
         call('Viewport','PlayerController','GetViewportSize'),
         call('Ratio','KismetMathLibrary','Divide_DoubleDouble'),
         call('Height','KismetMathLibrary','Max'),get('VFOV','CamVerticalFOV'),
         call('Half','KismetMathLibrary','Multiply_DoubleDouble'),
         call('Tan','KismetMathLibrary','DegTan'),
         call('WidthTan','KismetMathLibrary','Multiply_DoubleDouble'),
         call('Atan','KismetMathLibrary','DegAtan'),
         call('Double','KismetMathLibrary','Multiply_DoubleDouble'),
         call('FOV','CameraComponent','SetFieldOfView')],
        [('880B433444E3718B62214A9F43D2120C.then','CastPC.execute'),
         ('PC.ReturnValue','CastPC.Object'),('CastPC.As플레이어 컨트롤러','Viewport.self'),
         ('Viewport.SizeX','Ratio.A'),('Viewport.SizeY','Height.A'),('Height.ReturnValue','Ratio.B'),
         ('VFOV.CamVerticalFOV','Half.A'),('Half.ReturnValue','Tan.A'),
         ('Tan.ReturnValue','WidthTan.A'),('Ratio.ReturnValue','WidthTan.B'),
         ('WidthTan.ReturnValue','Atan.A'),('Atan.ReturnValue','Double.A'),
         ('Double.ReturnValue','FOV.InFieldOfView'),('Camera.FollowCamera','FOV.self'),
         ('CastPC.then','FOV.execute')],
        [('Height','B',1),('Half','B',.5),('Double','B',2)])
    block(P,'UpdateLockOnRotation','DS3 camera: target height and vertical composition bias',
        [get('Camera','FollowCamera'),call('CameraLoc','SceneComponent','K2_GetComponentLocation'),
         call('Look','KismetMathLibrary','FindLookAtRotation'),call('Break','KismetMathLibrary','BreakRotator'),
         get('VFOV','CamVerticalFOV'),get('Shift','CamLockShiftRatio'),
         call('Half','KismetMathLibrary','Multiply_DoubleDouble'),call('Tan','KismetMathLibrary','DegTan'),
         call('ShiftTan','KismetMathLibrary','Multiply_DoubleDouble'),call('Bias','KismetMathLibrary','DegAtan'),
         call('Pitch','KismetMathLibrary','Subtract_DoubleDouble'),call('Clamp','KismetMathLibrary','FClamp'),
         get('Min','CamLockPitchMin'),get('Max','CamLockPitchMax')],
        [('Camera.FollowCamera','CameraLoc.self'),('CameraLoc.ReturnValue','Look.Start'),
         ('7F68B4E34E26A0AC6BDA8A9A9E1CE760.ReturnValue','Look.Target'),
         ('Look.ReturnValue','Break.InRot'),('VFOV.CamVerticalFOV','Half.A'),
         ('Half.ReturnValue','Tan.A'),('Tan.ReturnValue','ShiftTan.A'),
         ('Shift.CamLockShiftRatio','ShiftTan.B'),('ShiftTan.ReturnValue','Bias.A'),
         ('Break.Pitch','Pitch.A'),('Bias.ReturnValue','Pitch.B'),('Pitch.ReturnValue','Clamp.Value'),
         ('Min.CamLockPitchMin','Clamp.Min'),('Max.CamLockPitchMax','Clamp.Max'),
         ('Clamp.ReturnValue','E1043B3545A02EE6DE1306B365F03362.Pitch')],
        [('Half','B',.5)])
    block(P,'ToggleLockOn','DS3 camera: acquisition uses the same 15m range as retention',
        [call('Distance','Actor','GetHorizontalDistanceTo'),get('Range','CamLockRange'),
         call('InRange','KismetMathLibrary','LessEqual_DoubleDouble'),node('Gate','branch')],
        [('A4AF873A46A55C669D6B4F9A15EB8695.then','Gate.execute'),
         ('B1FF5E9E47D1A8E811577ABAB6DFA317.ReturnValue','Distance.OtherActor'),
         ('Distance.ReturnValue','InRange.A'),('Range.CamLockRange','InRange.B'),
         ('InRange.ReturnValue','Gate.Condition'),('Gate.then','7F4851234DF768A718360E8AA09EE959.execute')])


def attack_start():
    block(P,'StartComboStep','DS3 action phases: record startup, stop locomotion, consume one queue slot',
        [put('ClearDodge','bDodgeBuffered'),call('Now','GameplayStatics','GetTimeSeconds'),
         put('Start','AttackStartTime'),get('Movement','CharacterMovement'),
         call('Stop','MovementComponent','StopMovementImmediately'),
         put('Duration','CurrentAttackDuration')],
        [('FBF00D024FBA8441C0A561ABFBEF0B1B.then','ClearDodge.execute'),
         ('ClearDodge.then','Start.execute'),('Now.ReturnValue','Start.AttackStartTime'),
         ('Start.then','Stop.execute'),('Movement.CharacterMovement','Stop.self'),
         ('Stop.then','0B46362E4BA64754693BA1A36832A00D.execute'),
         ('362DD75A476C97F9E67467895F5489B1.then','Duration.execute'),
         ('2FF4905046BC4E6E45EC51A79F55655E.ReturnValue','Duration.CurrentAttackDuration'),
         ('Duration.then','F57424704E1B45030AAEB694DF325AAD.execute')],
        [('ClearDodge','bDodgeBuffered','false')])
    S.disconnect_pin(P,'Move','EE2AED184F5E930A5BCC2D95FD886837','then')
    block(P,'UpdateLockOnRotation','DS3 action phases: attacks and rolls bypass ordinary body homing',
        [get('State','ActionState'),call('Attack','KismetMathLibrary','EqualEqual_ByteByte'),
         call('Busy','KismetMathLibrary','BooleanOR'),call('FreeOrient','KismetMathLibrary','Not_PreBool')],
        [('State.ActionState','Attack.A'),('Attack.ReturnValue','Busy.A'),
         ('936E73FE4CACB7BDB7413E9731F9DC57.ReturnValue','Busy.B'),
         ('Busy.ReturnValue','2863F7D14E733373E8B01B84663A3693.Condition'),
         ('Busy.ReturnValue','FreeOrient.A'),
         ('FreeOrient.ReturnValue','91CFA92D4AFDC83B656A2B9E55A1BD18.bOrientRotationToMovement')],
        [('Attack','B',4)])


def steering():
    entry=H.function(P,'UpdateAttackSteering',[('DeltaSeconds','float')])
    block(P,'UpdateAttackSteering','DS3 action phases: limited startup aim then committed sword trajectory',
        [get('State','ActionState'),call('Attack','KismetMathLibrary','EqualEqual_ByteByte'),
         call('Now','GameplayStatics','GetTimeSeconds'),get('Start','AttackStartTime'),
         call('Elapsed','KismetMathLibrary','Subtract_DoubleDouble'),get('Duration','CurrentAttackDuration'),
         get('Ratio','AttackTrackingRatio'),call('Window','KismetMathLibrary','Multiply_DoubleDouble'),
         call('Early','KismetMathLibrary','Less_DoubleDouble'),call('Both','KismetMathLibrary','BooleanAND'),
         node('Gate','branch'),get('Target','LockOnTarget'),call('Valid','KismetSystemLibrary','IsValid'),
         node('Mode','branch'),call('SelfLoc','Actor','K2_GetActorLocation'),call('TargetLoc','Actor','K2_GetActorLocation'),
         call('Look','KismetMathLibrary','FindLookAtRotation'),call('LookBreak','KismetMathLibrary','BreakRotator'),
         call('LockYaw','KismetMathLibrary','MakeRotator'),
         call('Control','Pawn','GetControlRotation'),call('ControlBreak','KismetMathLibrary','BreakRotator'),
         call('ControlYaw','KismetMathLibrary','MakeRotator'),call('Forward','KismetMathLibrary','GetForwardVector'),
         call('Right','KismetMathLibrary','GetRightVector'),get('Input','LastMoveInput'),
         call('InputBreak','KismetMathLibrary','BreakVector2D'),
         call('ForwardMove','KismetMathLibrary','Multiply_VectorFloat'),
         call('RightMove','KismetMathLibrary','Multiply_VectorFloat'),call('Move','KismetMathLibrary','Add_VectorVector'),
         call('Zero','KismetMathLibrary','Vector_IsNearlyZero'),node('FreeGate','branch'),
         call('FreeYaw','KismetMathLibrary','Conv_VectorToRotator'),
         call('Current','Actor','K2_GetActorRotation'),get('TurnRate','AttackTurnRate'),
         call('LockInterp','KismetMathLibrary','RInterpTo_Constant'),call('FreeInterp','KismetMathLibrary','RInterpTo_Constant'),
         call('SetLock','Actor','K2_SetActorRotation'),call('SetFree','Actor','K2_SetActorRotation')],
        [(entry+'.then','Gate.execute'),('State.ActionState','Attack.A'),
         ('Now.ReturnValue','Elapsed.A'),('Start.AttackStartTime','Elapsed.B'),
         ('Duration.CurrentAttackDuration','Window.A'),('Ratio.AttackTrackingRatio','Window.B'),
         ('Elapsed.ReturnValue','Early.A'),('Window.ReturnValue','Early.B'),
         ('Attack.ReturnValue','Both.A'),('Early.ReturnValue','Both.B'),('Both.ReturnValue','Gate.Condition'),
         ('Gate.then','Mode.execute'),('Target.LockOnTarget','Valid.Object'),('Valid.ReturnValue','Mode.Condition'),
         ('Target.LockOnTarget','TargetLoc.self'),('SelfLoc.ReturnValue','Look.Start'),('TargetLoc.ReturnValue','Look.Target'),
         ('Look.ReturnValue','LookBreak.InRot'),('LookBreak.Yaw','LockYaw.Yaw'),
         ('Control.ReturnValue','ControlBreak.InRot'),('ControlBreak.Yaw','ControlYaw.Yaw'),
         ('ControlYaw.ReturnValue','Forward.InRot'),('ControlYaw.ReturnValue','Right.InRot'),
         ('Input.LastMoveInput','InputBreak.InVec'),('InputBreak.Y','ForwardMove.B'),('Forward.ReturnValue','ForwardMove.A'),
         ('InputBreak.X','RightMove.B'),('Right.ReturnValue','RightMove.A'),
         ('ForwardMove.ReturnValue','Move.A'),('RightMove.ReturnValue','Move.B'),('Move.ReturnValue','Zero.A'),
         ('Move.ReturnValue','FreeYaw.InVec'),('Mode.else','FreeGate.execute'),('Zero.ReturnValue','FreeGate.Condition'),
         ('Current.ReturnValue','LockInterp.Current'),('Current.ReturnValue','FreeInterp.Current'),
         ('LockYaw.ReturnValue','LockInterp.Target'),('FreeYaw.ReturnValue','FreeInterp.Target'),
         (entry+'.DeltaSeconds','LockInterp.DeltaTime'),(entry+'.DeltaSeconds','FreeInterp.DeltaTime'),
         ('TurnRate.AttackTurnRate','LockInterp.InterpSpeed'),('TurnRate.AttackTurnRate','FreeInterp.InterpSpeed'),
         ('Mode.then','SetLock.execute'),('LockInterp.ReturnValue','SetLock.NewRotation'),
         ('FreeGate.else','SetFree.execute'),('FreeInterp.ReturnValue','SetFree.NewRotation')],
        [('Attack','B',4)])
    block(P,'EventGraph','DS3 action phases: evaluate startup steering before blade traces',
        [call('Steer',P,'UpdateAttackSteering')],
        [('B009E31544426A949F9522890F075C27.then','Steer.execute'),
         ('B009E31544426A949F9522890F075C27.DeltaSeconds','Steer.DeltaSeconds'),
         ('Steer.then','8C6AB0D441E9CA037D86CCB557790939.execute')])


def queue():
    for graph, source, other in [('TryEnterAttack','2AF72C9549E4394F4C579FBC127F6506','bDodgeBuffered'),
                                 ('TryEnterDodge','CABEB49B4B507C09F1C9B6918A2F40B9','bAttackBuffered')]:
        block(P,graph,'DS3 input queue: latest accepted action replaces the previous action',
              [put('ClearOther',other)],[(source+'.then','ClearOther.execute')],[('ClearOther',other,'false')])
    # Stamp both early attack buffering and the existing latter-half roll queue.
    for graph, sources in [('TryEnterAttack',['2AF72C9549E4394F4C579FBC127F6506','2249D23D42975BC116AED2ABBEA93F4F']),
                           ('TryEnterDodge',['CABEB49B4B507C09F1C9B6918A2F40B9','34C8F3BB43380BBA7B22519D2529DF8F'])]:
        for i,source in enumerate(sources):
            # Splice before the already present setter without replacing it.
            incoming=next(c for c in S.get_connections(P,graph) if c.target_node_id==source and c.target_pin_name=='execute')
            block(P,graph,'DS3 input queue: accepted intent expires (%d)'%i,
                  [call('Now','GameplayStatics','GetTimeSeconds'),get('Life','ActionQueueLifetime'),
                   call('Add','KismetMathLibrary','Add_DoubleDouble'),put('Expiry','QueuedActionExpires')],
                  [(incoming.source_node_id+'.'+incoming.source_pin_name,'Expiry.execute'),
                   ('Now.ReturnValue','Add.A'),('Life.ActionQueueLifetime','Add.B'),
                   ('Add.ReturnValue','Expiry.QueuedActionExpires'),('Expiry.then',source+'.execute')])
    entry=H.function(P,'UpdateActionRequests')
    block(P,'UpdateActionRequests','DS3 input queue: expire stale actions; held guard resumes only in locomotion',
        [call('Now','GameplayStatics','GetTimeSeconds'),get('Expiry','QueuedActionExpires'),
         call('Expired','KismetMathLibrary','Greater_DoubleDouble'),node('QueueGate','branch'),
         put('ClearAttack','bAttackBuffered'),put('ClearDodge','bDodgeBuffered'),
         get('Guard','bGuardRequested'),get('State','ActionState'),call('Free','KismetMathLibrary','EqualEqual_ByteByte'),
         call('Both','KismetMathLibrary','BooleanAND'),node('GuardGate','branch'),call('Block',P,'TryEnterBlock')],
        [(entry+'.then','QueueGate.execute'),('Now.ReturnValue','Expired.A'),('Expiry.QueuedActionExpires','Expired.B'),
         ('Expired.ReturnValue','QueueGate.Condition'),('QueueGate.then','ClearAttack.execute'),
         ('ClearAttack.then','ClearDodge.execute'),('ClearDodge.then','GuardGate.execute'),
         ('QueueGate.else','GuardGate.execute'),('Guard.bGuardRequested','Both.A'),
         ('State.ActionState','Free.A'),('Free.ReturnValue','Both.B'),('Both.ReturnValue','GuardGate.Condition'),
         ('GuardGate.then','Block.execute')],
        [('ClearAttack','bAttackBuffered','false'),('ClearDodge','bDodgeBuffered','false'),('Free','B',5)])
    steer=next(n.node_id for n in S.get_nodes_in_graph(P,'EventGraph',0,'Update Attack Steering',False))
    block(P,'EventGraph','DS3 input queue: update expiration and held requests each tick',
        [call('Requests',P,'UpdateActionRequests')],
        [(steer+'.then','Requests.execute'),('Requests.then','8C6AB0D441E9CA037D86CCB557790939.execute')])
    block(P,'EventGraph','DS3 held guard: request on press and clear on release or cancel',
        [put('Press','bGuardRequested'),put('Release','bGuardRequested'),put('Cancel','bGuardRequested'),
         call('ExitCancel',P,'ExitBlock')],
        [('F5AC2B4944A169649EF26DBD8543FFAE.Started','Press.execute'),
         ('Press.then','95C0B4AE4BE58B203202BC910965CD59.execute'),
         ('F5AC2B4944A169649EF26DBD8543FFAE.Completed','Release.execute'),
         ('Release.then','E2E90A53400702B572FAA6830E3165C6.execute'),
         ('F5AC2B4944A169649EF26DBD8543FFAE.Canceled','Cancel.execute'),('Cancel.then','ExitCancel.execute')],
        [('Press','bGuardRequested','true'),('Release','bGuardRequested','false'),('Cancel','bGuardRequested','false')])


def phase_windows():
    H.variable(P,'AttackRollCancelRatio','real',.60)
    H.variable(P,'bAttackRollWindowOpen','bool','false')
    assert S.set_variable_instance_editable(P,'AttackRollCancelRatio',True)
    event=H.function(P,'OnAttackRollWindowOpen')
    block(P,'OnAttackRollWindowOpen','DS3 phases: dodge cancel opens before combo input',
        [get('State','ActionState'),call('Attack','KismetMathLibrary','EqualEqual_ByteByte'),
         node('Gate','branch'),put('Open','bAttackRollWindowOpen'),get('Queued','bDodgeBuffered'),
         node('Consume','branch'),call('Dodge',P,'TryEnterDodge')],
        [(event+'.then','Gate.execute'),('State.ActionState','Attack.A'),('Attack.ReturnValue','Gate.Condition'),
         ('Gate.then','Open.execute'),('Open.then','Consume.execute'),
         ('Queued.bDodgeBuffered','Consume.Condition'),('Consume.then','Dodge.execute')],
        [('Attack','B',4),('Open','bAttackRollWindowOpen','true')])
    block(P,'StartComboStep','DS3 phases: separate .60 dodge cancel and .68 combo windows',
        [put('Reset','bAttackRollWindowOpen'),get('Ratio','AttackRollCancelRatio'),
         call('Delay','KismetMathLibrary','Multiply_DoubleDouble'),
         call('Timer','KismetSystemLibrary','K2_SetTimer')],
        [('647F83974787827293060DBB9BE53B5B.then','Reset.execute'),
         ('Reset.then','A789130B4AE06691BFF35C8AAC67CAC6.execute'),
         ('3DFA620643BF19E40FC359A5B8256700.then','Timer.execute'),
         ('Timer.then','AFCFDCB749D0974F8883DD8A18287391.execute'),
         ('2FF4905046BC4E6E45EC51A79F55655E.ReturnValue','Delay.A'),
         ('Ratio.AttackRollCancelRatio','Delay.B'),('Delay.ReturnValue','Timer.Time')],
        [('Reset','bAttackRollWindowOpen','false'),('Timer','FunctionName','OnAttackRollWindowOpen')])
    block(P,'TryEnterDodge','DS3 phases: independent dodge window and cancel old timer',
        [get('Window','bAttackRollWindowOpen'),
         call('Clear','KismetSystemLibrary','K2_ClearTimer')],
        [('Window.bAttackRollWindowOpen','993D1F6D4D5D1FAEAC95DC999BD39247.B'),
         ('F77A988B42CCA1AC02498A81DFE7A74E.then','Clear.execute'),
         ('EACC12454FED994EF77DBABF7EDD313E.ReturnValue','Clear.Object'),
         ('Clear.then','13E5C73C445CE949A14304B0FAB1369D.execute')],
        [('Clear','FunctionName','OnAttackRollWindowOpen')])


def verify_save():
    unreal.BlueprintEditorLibrary.compile_blueprint(H.asset(P))
    print('STATUS',H.asset(P).get_editor_property('status'))
    assert str(H.asset(P).get_editor_property('status')).endswith('UP_TO_DATE: 0>') or 'UP_TO_DATE' in str(H.asset(P).get_editor_property('status'))
    unreal.EditorAssetLibrary.save_asset(P,False)
    # Components of an existing placed player can override the SCS template.
    cdo=unreal.get_default_object(unreal.load_class(None,P+'.BP_Player_Combat_C'))
    template=cdo.get_component_by_class(unreal.SpringArmComponent)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        if 'BP_Player_Combat' in actor.get_class().get_name():
            boom=actor.get_component_by_class(unreal.SpringArmComponent)
            actor.modify();boom.modify()
            for prop in ['target_arm_length','target_offset','socket_offset','relative_location',
                         'enable_camera_lag','camera_lag_speed','camera_lag_max_distance']:
                boom.set_editor_property(prop,template.get_editor_property(prop))
            print('MODIFIED: placed player',actor.get_path_name())
    unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()


def apply():
    """Run with PIE stopped. SCS, graph, sequence and backups are preserved."""
    setup()
    camera()
    attack_start()
    steering()
    queue()
    phase_windows()
    verify_save()
