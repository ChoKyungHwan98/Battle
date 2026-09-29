"""Timed PIE checks that use the boss action montage and its actual contact path."""
import unreal
import TestSoulsHits as T
import json

samples=[]
observer=None
start_time=0
current_index=0


def observe():
    global samples,observer,start_time
    samples=[]
    start_time=unreal.GameplayStatics.get_time_seconds(T.world())
    prev={}
    def tick(delta):
        b,p=T.boss(),T.player()
        mesh=b.get_component_by_class(unreal.SkeletalMeshComponent)
        action=b.get_editor_property('Actions')[current_index]
        sockets=[str(x) for x in action.get_editor_property('HitSockets')] or ['hand_l']
        if current_index==6:sockets=['hand_l','hand_r']
        hands=[mesh.get_socket_location(socket) for socket in sockets]
        center=p.get_actor_location()
        capsule=p.get_component_by_class(unreal.CapsuleComponent)
        gaps=[]
        for hand in hands:
            dx=hand.x-center.x;dy=hand.y-center.y;dz=hand.z-center.z
            horizontal=max(0,(dx*dx+dy*dy)**.5-capsule.get_unscaled_capsule_radius())
            vertical=max(0,abs(dz)-capsule.get_unscaled_capsule_half_height())
            gaps.append((horizontal*horizontal+vertical*vertical)**.5)
        attack_socket=str(b.get_editor_property('AttackSocket'))
        attack_hand=mesh.get_socket_location(attack_socket)
        trace_name=''
        probes={}
        if b.get_editor_property('bHitWindowOpen'):
            trace=unreal.SystemLibrary.sphere_trace_single(T.world(),prev.get(attack_socket,attack_hand),attack_hand,
                b.get_editor_property('AttackHitRadius'),unreal.TraceTypeQuery.ECC_VISIBILITY,False,[b],unreal.DrawDebugTrace.NONE,False)
            trace_name=trace.export_text()[:320] if trace else ''
        prev[attack_socket]=attack_hand
        if min(gaps)<230:
            for probe_socket in set(sockets):
                probe_hand=mesh.get_socket_location(probe_socket)
                for radius in [110,130,150,180,220]:
                    hit=unreal.SystemLibrary.sphere_trace_single(T.world(),prev.get('probe_'+probe_socket,probe_hand),probe_hand,
                        radius,unreal.TraceTypeQuery.ECC_VISIBILITY,False,[b],unreal.DrawDebugTrace.NONE,False)
                    desc=hit.export_text() if hit else ''
                    probes[probe_socket+':'+str(radius)]='player' if 'BP_Player_Combat' in desc else ('other' if desc else '')
                prev['probe_'+probe_socket]=probe_hand
        samples.append({'t':round(unreal.GameplayStatics.get_time_seconds(T.world())-start_time,3),
          'hands':[[round(x,1) for x in hand.to_tuple()] for hand in hands],'player':[round(x,1) for x in center.to_tuple()],
          'boss':[round(x,1) for x in b.get_actor_location().to_tuple()],
          'boss_state':b.get_editor_property('BossState').export_text(),
          'lunge_active':int(b.get_editor_property('bLungeActive')),
          'dash_remaining':round(b.get_editor_property('AttackDashRemaining'),1),
          'gap':round(min(gaps),1),
          'socket_gaps':{socket:round(gap,1) for socket,gap in zip(sockets,gaps)},
          'attack_socket':attack_socket,'attack_radius':b.get_editor_property('AttackHitRadius'),'trace':trace_name,
          'probes':probes,
          'open':int(b.get_editor_property('bHitWindowOpen')),
          'hp':round(p.get_editor_property('CurrentHealth'),1)})
    observer=unreal.register_slate_post_tick_callback(tick)
    return True


def stop_observing():
    global observer
    if observer is not None:unreal.unregister_slate_post_tick_callback(observer);observer=None
    path=unreal.Paths.project_saved_dir()+f'VibeUE/boss-real-contact-{current_index}.json'
    with open(path,'w',encoding='utf-8') as f:json.dump(samples,f,indent=2)
    print('CONTACT_SAMPLES',len(samples),'PATH',path,'MIN_GAP',min((s['gap'] for s in samples),default=None),'OPEN_MIN',min((s['gap'] for s in samples if s['open']),default=None))
    return True


def begin(index=0,distance=285):
    global current_index
    T.setup(distance)
    current_index=index
    b=T.boss()
    action=b.get_editor_property('Actions')[index]
    if index==6:
        movement=b.get_component_by_class(unreal.CharacterMovementComponent)
        movement.set_component_tick_enabled(True)
        movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)
    observe()
    try:
        b.call_method('RequestCombatAction',(index,))
    except Exception as exc:
        print('REQUEST_ERROR',repr(exc),'STATE',b.get_editor_property('BossState').export_text(),'SELECTED',b.get_editor_property('SelectedSlot'),'ACTIVE',b.get_editor_property('ActiveAction'))
        return -1
    b.set_actor_tick_enabled(True)
    return int(b.get_editor_property('ActiveAction')==action)


def phase():
    return T.boss().get_editor_property('BossState').export_text()


def active_window():
    return int(T.boss().get_editor_property('bHitWindowOpen'))


def montage():
    mesh=T.boss().get_component_by_class(unreal.SkeletalMeshComponent)
    m=mesh.get_anim_instance().get_current_active_montage()
    return m.get_name() if m else ''


def first_scenario():
    name="__import__('TestBossRealContact')";hits="__import__('TestSoulsHits')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    def wait(t):steps.append({'action':'wait','seconds':t})
    def assert_num(e,v=1,tol=0):
        steps.append({'action':'python_assert_number','expression':e,
                      'expected':v,'operator':'eq','tolerance':tol})
    assert_num(f'{name}.begin(0,285)');wait(.12)
    assert_num(f'int("Attack" in {name}.phase())')
    assert_num(f'int({name}.montage()!="")')
    wait(.9)
    assert_num(f'{name}.active_window()')
    steps.append({'action':'capture_game','name':'boss-left-real-contact'})
    wait(.25)
    assert_num(f'int({name}.stop_observing())')
    assert_num(f'{name}.raw_health()',1890)
    steps.append({'action':'assert_log','not_contains':'LogScript: Warning'})
    return {'name':'Boss left swing uses actual montage contact and hurts stationary player',
            'steps':steps,'teardown':{'stop_pie':True}}


def raw_health():
    return T.player().get_editor_property('CurrentHealth')


def prepare_lock(distance):
    T.setup(distance)
    p=T.player()
    if not p.get_editor_property('LockOnTarget'):p.call_method('ToggleLockOn')
    return bool(p.get_editor_property('LockOnTarget'))


def locked_left_scenario():
    Q="__import__('TestBossRealContact')";C="__import__('TestDS3CameraFraming')"
    return {'name':'Actual boss left contact while camera lock is established',
      'steps':[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
       {'action':'python_assert_number','expression':f'int({Q}.prepare_lock(285))','expected':1,'operator':'eq'},
       {'action':'wait','seconds':1.2},
       {'action':'python_assert_number','expression':f'{Q}.begin(0,285)','expected':1,'operator':'eq'},
       {'action':'wait','seconds':1.03},
       {'action':'python_assert_number','expression':f'int({C}.record("lock-during-left-attack"))','expected':1,'operator':'eq'},
       {'action':'capture_game','name':'locked-boss-left-contact'},
       {'action':'wait','seconds':.25},
       {'action':'python_assert_number','expression':f'int({Q}.stop_observing())','expected':1,'operator':'eq'},
       {'action':'python_assert_number','expression':f'{Q}.raw_health()','expected':1890,'operator':'eq'}],
      'teardown':{'stop_pie':True}}


def matrix_scenario():
    name="__import__('TestBossRealContact')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20}]
    for index,distance,duration in [(1,285,1.9),(2,285,2.4),(3,285,3.6),(4,285,6.5),(5,285,3.0),(6,600,2.8)]:
        steps.append({'action':'python_assert_number','expression':f'{name}.begin({index},{distance})','expected':1,'operator':'eq'})
        steps.append({'action':'wait','seconds':duration})
        steps.append({'action':'python_assert_number','expression':f'int({name}.stop_observing())','expected':1,'operator':'eq'})
        steps.append({'action':'capture_game','name':f'boss-pattern-{index}-after'})
        steps.append({'action':'wait','seconds':.5})
    return {'name':'Measure actual montage contact of boss attack actions 1-6','steps':steps,'teardown':{'stop_pie':True}}


def single_scenario(index,distance,duration,expected_health=None):
    name="__import__('TestBossRealContact')"
    steps=[{'action':'start_pie'},{'action':'wait_for_pie','timeout_seconds':20},
       {'action':'python_assert_number','expression':f'{name}.begin({index},{distance})','expected':1,'operator':'eq'},
       {'action':'wait','seconds':duration},
       {'action':'python_assert_number','expression':f'int({name}.stop_observing())','expected':1,'operator':'eq'}]
    if expected_health is not None:
        steps.append({'action':'python_assert_number','expression':f'{name}.raw_health()',
          'expected':expected_health,'operator':'eq'})
    steps.append({'action':'capture_game','name':f'boss-action-{index}-at-{distance}cm'})
    return {'name':f'Measure boss action {index} at {distance}cm',
      'steps':steps,
      'teardown':{'stop_pie':True}}
