"""Add observational PIE logging through Unreal MCP. Never starts PIE."""
import unreal
import vibeue
import PolishSoulsHits as H
import ApplyBossAttackSteps as G

B, P, S = H.B, H.P, unreal.BlueprintService
node, call, get = H.node, H.call, H.get


class Row:
    def __init__(self, prefix):
        self.nodes, self.links, self.defaults = [], [], []
        self.last = None
        self.prefix = prefix

    def add(self, key, kind, source):
        ref = 'Field' + str(len(self.nodes))
        if kind == 'string':
            clean = ref + 'Clean'
            self.nodes += [call(clean, 'KismetStringLibrary', 'Replace'),
                           call(ref, 'KismetStringLibrary', 'Concat_StrStr')]
            self.links += [(source, clean+'.SourceString'), (clean+'.ReturnValue', ref+'.B')]
            self.defaults += [(clean, 'From', '|'), (clean, 'To', '/')]
            if self.last:
                join = ref+'Prefix'
                self.nodes.append(call(join, 'KismetStringLibrary', 'Concat_StrStr'))
                self.links += [(self.last, join+'.A'), (join+'.ReturnValue', ref+'.A')]
                self.defaults += [(join, 'B', '|'+key+'=')]
            else:
                self.defaults += [(ref, 'A', self.prefix+'|'+key+'=')]
        else:
            suffix = {'real': 'Double', 'int': 'Int', 'bool': 'Bool', 'vector': 'Vector'}[kind]
            self.nodes.append(call(ref, 'KismetStringLibrary', 'BuildString_'+suffix))
            self.links.append((source, ref+'.In'+suffix))
            self.defaults += [(ref, 'Prefix', '|'+key+'=')]
            if self.last:
                self.links.append((self.last, ref+'.AppendTo'))
            else:
                self.defaults.append((ref, 'AppendTo', self.prefix))
        self.last = ref+'.ReturnValue'


def build(path, graph, nodes, links=(), defaults=()):
    return G.build(path, graph, nodes, links, defaults)


def empty_body(path, graph):
    # Keep the returned Unreal Array alive; do not iterate its temporary structs
    # in a generator after the native array wrapper has gone out of scope.
    nodes = S.get_nodes_in_graph(path, graph, 0, '', False)
    return len(nodes) == 1 and nodes[0].node_type == 'K2Node_FunctionEntry'


def hook(path, graph, source, pin, function, event=None):
    # Match by the event parameter, allowing multiple distinct QA hooks per graph.
    for n in S.get_nodes_in_graph(path, graph, 0, '', False):
        if function == 'StartCombatQA' and 'Start Combat QA' in n.node_title:
            return
        if function == 'RecordCombatQACandidate' and 'Record Combat QACandidate' in n.node_title:
            return
        if event is not None and any(p.pin_name == 'Event' and p.default_value == event
                                    for p in S.get_node_pins(path, graph, n.node_id)):
            if 'Combat QA' in n.node_title:
                return
    targets = [(c.target_node_id, c.target_pin_name) for c in S.get_connections(path, graph)
               if c.source_node_id == source and c.source_pin_name == pin]
    ids = build(path, graph, [call('QALog', path, function)], defaults=[] if event is None
                else [('QALog', 'Event', event)])
    if targets:
        assert S.disconnect_pin(path, graph, source, pin)
    assert S.connect_nodes(path, graph, source, pin, ids['QALog'], 'execute')
    for dst, dpin in targets:
        assert S.connect_nodes(path, graph, ids['QALog'], 'then', dst, dpin)
    print('MODIFIED QA hook', path, graph, event or function)


def common(row, event_source, role):
    row.nodes += [node('Self', 'spawner_key', key='NODE /Script/BlueprintGraph.K2Node_Self'),
                  call('Name', 'KismetSystemLibrary', 'GetObjectName'),
                  call('Map', 'GameplayStatics', 'GetCurrentLevelName'),
                  call('Now', 'GameplayStatics', 'GetTimeSeconds')]
    row.links.append(('Self.self', 'Name.Object'))
    row.add('event', 'string', event_source)
    row.add('boss', 'string', 'Name.ReturnValue')
    row.add('map', 'string', 'Map.ReturnValue')
    row.add('t', 'real', 'Now.ReturnValue')


def apply():
    assert not vibeue.exec_tool('EditorToolset.EditorAppToolset', 'IsPIERunning')
    for name, kind, value in [('bCombatQAEnabled', 'bool', 'true'),
                              ('CombatQAInterval', 'real', .2)]:
        H.variable(B, name, kind, value)
        assert S.set_variable_instance_editable(B, name, True)
    for path, name, params in [(B, 'RecordCombatQA', [('Event', 'string')]),
                               (B, 'RecordCombatQACandidate', []),
                               (B, 'RecordCombatQASample', []),
                               (B, 'StartCombatQA', []),
                               (P, 'RecordPlayerCombatQA', [('Event', 'string')])]:
        H.function(path, name, params)

    g = 'RecordCombatQA'
    if empty_body(B, g):
        e = G.entry(B, g)
        row = Row('[BATTLE_QA] v=1|role=boss')
        common(row, e+'.Event', 'boss')
        fields = [('state','StateDisplay','string'), ('slot','SelectedSlot','int'),
                  ('decision','UtilityDecisionCount','int'), ('choice','UtilityChoice','string'),
                  ('goap','GoapReason','string'), ('reason','TransitionReason','string'),
                  ('decision_distance','UtilityDistance','real'), ('hp','CurrentHealth','real'),
                  ('phase_two','bPhaseTwo','bool'), ('approach','bCombatApproachActive','bool'),
                  ('approach_goal','ApproachGoalDistance','real'),
                  ('attack_step','bAttackStepActive','bool'), ('step_progress','AttackStepProgress','real'),
                  ('strike_open','bPhysicalStrikeOpen','bool'), ('strike','PhysicalStrikeIndex','int'),
                  ('contact_recorded','bPhysicalStrikeHit','bool'),
                  ('direction_locked','bDirectionCommitted','bool')]
        for key, variable, kind in fields:
            ref = 'Value'+variable
            row.nodes.append(get(ref, variable)); row.add(key, kind, ref+'.'+variable)
        row.nodes += [call('Position','Actor','K2_GetActorLocation'), call('Velocity','Actor','GetVelocity'),
                      call('Speed','KismetMathLibrary','VSize'), call('Rotation','Actor','K2_GetActorRotation'),
                      call('Yaw','KismetMathLibrary','BreakRotator')]
        row.links += [('Velocity.ReturnValue','Speed.A'), ('Rotation.ReturnValue','Yaw.InRot')]
        row.add('pos','vector','Position.ReturnValue'); row.add('speed','real','Speed.ReturnValue')
        row.add('yaw','real','Yaw.Yaw')
        row.nodes += [get('Enabled','bCombatQAEnabled'),node('Gate','branch'),
                      call('WriteBoss','KismetSystemLibrary','PrintString'),
                      call('Player','GameplayStatics','GetPlayerCharacter'),node('PlayerCast','cast',target_class=P)]
        row.links += [(e+'.then','Gate.execute'), ('Enabled.bCombatQAEnabled','Gate.Condition'),
                      ('Gate.then','Map.execute'), ('Map.then','WriteBoss.execute'), (row.last,'WriteBoss.InString'),
                      ('WriteBoss.then','PlayerCast.execute'), ('Player.ReturnValue','PlayerCast.Object')]
        row.defaults += [('WriteBoss','bPrintToScreen','false'), ('WriteBoss','bPrintToLog','true')]
        ids = build(B,g,row.nodes,row.links,row.defaults)
        cast_pin = next(p.pin_name for p in S.get_node_pins(B,g,ids['PlayerCast'])
                        if not p.is_input and p.pin_name.startswith('As'))
        player = Row('[BATTLE_QA] v=1|role=player')
        # Reuse boss identity/time pure nodes from the first row.
        for key, kind, src in [('event','string',e+'.Event'), ('boss','string',ids['Name']+'.ReturnValue'),
                               ('map','string',ids['Map']+'.ReturnValue'), ('t','real',ids['Now']+'.ReturnValue')]:
            player.add(key,kind,src)
        for key, variable, kind in [('hp','CurrentHealth','real'),('stamina','CurrentStamina','real'),
                                   ('invincible','bInvincible','bool'),('guard','bGuardRequested','bool'),
                                   ('refunded','bDodgeRefunded','bool'),('dodge_paid','DodgePaidStamina','real')]:
            ref='Player'+variable
            player.nodes.append(node(ref,'member_get',**{'class':P,'member':variable}))
            player.links.append((ids['PlayerCast']+'.'+cast_pin,ref+'.self'))
            player.add(key,kind,ref+'.'+variable)
        player.nodes += [call('PlayerPos','Actor','K2_GetActorLocation'),call('PlayerVelocity','Actor','GetVelocity'),
                         call('PlayerSpeed','KismetMathLibrary','VSize'),
                         node('PlayerMovement','member_get',**{'class':'Character','member':'CharacterMovement'}),
                         node('WalkSpeed','member_get',**{'class':'CharacterMovementComponent','member':'MaxWalkSpeed'})]
        for ref in ('PlayerPos','PlayerVelocity','PlayerMovement'):
            player.links.append((ids['PlayerCast']+'.'+cast_pin,ref+'.self'))
        player.links += [('PlayerVelocity.ReturnValue','PlayerSpeed.A'),
                         ('PlayerMovement.CharacterMovement','WalkSpeed.self')]
        player.add('pos','vector','PlayerPos.ReturnValue');player.add('speed','real','PlayerSpeed.ReturnValue')
        player.add('max_walk_speed','real','WalkSpeed.MaxWalkSpeed')
        player.nodes.append(call('WritePlayer','KismetSystemLibrary','PrintString'))
        player.links += [(ids['PlayerCast']+'.then','WritePlayer.execute'),(player.last,'WritePlayer.InString')]
        player.defaults += [('WritePlayer','bPrintToScreen','false'),('WritePlayer','bPrintToLog','true')]
        build(B,g,player.nodes,player.links,player.defaults)

    g='RecordCombatQACandidate'
    if empty_body(B,g):
        e=G.entry(B,g);row=Row('[BATTLE_QA] v=1|role=candidate')
        row.nodes += [node('Self','spawner_key',key='NODE /Script/BlueprintGraph.K2Node_Self'),
                      call('Name','KismetSystemLibrary','GetObjectName'),call('Now','GameplayStatics','GetTimeSeconds'),
                      get('Decision','UtilityDecisionCount'),call('NextDecision','KismetMathLibrary','Add_IntInt')]
        row.links += [('Self.self','Name.Object'),('Decision.UtilityDecisionCount','NextDecision.A')]
        row.defaults.append(('NextDecision','B',1))
        row.add('boss','string','Name.ReturnValue'); row.add('t','real','Now.ReturnValue')
        row.add('decision','int','NextDecision.ReturnValue')
        for key,var,kind in [('slot','EvaluatedSlot','int'),('score','ScoreScratch','real'),
                             ('reason','ScoreReason','string'),('distance','UtilityDistance','real')]:
            row.nodes.append(get('Value'+var,var)); row.add(key,kind,'Value'+var+'.'+var)
        row.nodes += [get('Enabled','bCombatQAEnabled'),node('Gate','branch'),call('Write','KismetSystemLibrary','PrintString')]
        row.links += [(e+'.then','Gate.execute'),('Enabled.bCombatQAEnabled','Gate.Condition'),
                      ('Gate.then','Write.execute'),(row.last,'Write.InString')]
        row.defaults += [('Write','bPrintToScreen','false'),('Write','bPrintToLog','true')]
        build(B,g,row.nodes,row.links,row.defaults)

    g='RecordCombatQASample'
    if empty_body(B,g):
        build(B,g,[call('Sample',B,'RecordCombatQA')],[(G.entry(B,g)+'.then','Sample.execute')], [('Sample','Event','sample')])
    g='StartCombatQA'
    if empty_body(B,g):
        build(B,g,[call('Start',B,'RecordCombatQA'),get('Enabled','bCombatQAEnabled'),node('Gate','branch'),
                   node('Self','spawner_key',key='NODE /Script/BlueprintGraph.K2Node_Self'),
                   get('Interval','CombatQAInterval'),call('Bound','KismetMathLibrary','FClamp'),
                   call('Timer','KismetSystemLibrary','K2_SetTimer')], [
            (G.entry(B,g)+'.then','Start.execute'),('Start.then','Gate.execute'),
            ('Enabled.bCombatQAEnabled','Gate.Condition'),('Gate.then','Timer.execute'),
            ('Self.self','Timer.Object'),('Interval.CombatQAInterval','Bound.Value'),('Bound.ReturnValue','Timer.Time')], [
            ('Start','Event','session_start'),('Bound','Min',.1),('Bound','Max',1),
            ('Timer','FunctionName','RecordCombatQASample'),('Timer','bLooping','true'),('Timer','bMaxOncePerFrame','true')])

    g='RecordPlayerCombatQA'
    if empty_body(P,g):
        ids=build(P,g,[call('Boss','GameplayStatics','GetActorOfClass'),node('BossCast','cast',target_class=B)], [
            (G.entry(P,g)+'.then','Boss.execute'),('Boss.then','BossCast.execute'),('Boss.ReturnValue','BossCast.Object')], [
            ('Boss','ActorClass',H.asset(B).generated_class().get_path_name())])
        pin=next(p.pin_name for p in S.get_node_pins(P,g,ids['BossCast']) if not p.is_input and p.pin_name.startswith('As'))
        build(P,g,[call('Log',B,'RecordCombatQA')],[(ids['BossCast']+'.then','Log.execute'),
              (ids['BossCast']+'.'+pin,'Log.self'),(G.entry(P,g)+'.Event','Log.Event')])

    for graph,src,pin,fn,event in [
            ('BeginBossEncounter','1BF981764839ADC48DDF85BB27B80922','then','StartCombatQA',None),
            ('TransitionBossState','EB55C9FD42E38ADCA38EB8A1D279B9F9','then','RecordCombatQA','state'),
            ('ChooseCombatAction','4BB23F1A4CEFBCC3BC1E34928D06118E','then','RecordCombatQA','choice'),
            ('EvaluateCombatUtility','DC73785440581789532D82BB7C97A1D0','then','RecordCombatQACandidate',None),
            ('BeginPhysicalStrike','DE8526C0427109069186F6B38E480CB5','then','RecordCombatQA','strike_begin'),
            ('EndPhysicalStrike','989B412B439F181D1017C885F1702A64','then','RecordCombatQA','strike_end'),
            ('ResolvePhysicalContact','F51F95A3419BA2A6A4BC4EAF56F757D3','then','RecordCombatQA','contact_submitted')]:
        hook(B,graph,src,pin,fn,event)
    for graph,src,event in [
            ('RecordSuccessfulDodge','DA0E38FB41E29537429CB282BAACAB9F','dodge_accepted'),
            ('TryEnterBlock','1B7D9968483926A082F4DAAE474F7AB0','guard_begin'),
            ('ExitBlock','A379DA644956A49CC46416B48498BDEF','guard_end'),
            ('EventGraph','B3F88E424E10155F3D1C29B11F8E9B71','player_damage'),
            ('EventGraph','11450E884ADCC69F46D806B9A860F3C2','stamina_refund')]:
        hook(P,graph,src,'then','RecordPlayerCombatQA',event)
    for path in (B,P):
        result=S.compile_blueprint(path)
        print('COMPILE',path,result.success,list(result.errors),list(result.warnings))
        assert result.success and result.num_errors == 0 and not result.warnings
        assert unreal.EditorAssetLibrary.save_asset(path)
        print('SAVED',path)
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if actor.get_class().get_path_name()==H.asset(B).generated_class().get_path_name():
            actor.modify()
            actor.get_component_by_class(unreal.CapsuleComponent).set_collision_response_to_channel(
                unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_IGNORE)
            print('MODIFIED restored placed boss Visibility Ignore',actor.get_name())
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()


if __name__ == '__main__':
    apply()
