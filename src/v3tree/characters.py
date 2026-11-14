"""Index character identities, their script handles and operations at source positions.

A template identifies a design, not a unique runtime object. Scope names are
qualified by their defining script object. Variable slots can have several
writers; keep the slot in the graph instead of equating its values.
"""
import re
from collections import defaultdict, deque

from .clausewitz import unquote
from .sources import loc_resolve

IDENT = re.compile(r'^[\w-]+$')
HANDLE = re.compile(r'(?:^|\.)(scope|var|global_var):([\w-]+)')
LOC_HANDLE = re.compile(r"""(?:SCOPE\.sCharacter|GetGlobalVariable|(?:\bVar|GetVariable))\(\s*['"]([\w-]+)['"]\s*\)""", re.I)
TEMPLATE = {'has_template', 'template', 'is_template_used', 'character_template'}
POSITIONS = {'is_agitator':'agitator', 'ruler':'ruler', 'heir':'heir', 'ig_leader':'ig_leader',
             'is_general':'general', 'is_admiral':'admiral', 'is_politician':'politician'}
OPERATIONS = set("""kill_character retire_character exile_character exile_character_with_martyrdom
place_character_in_void transfer_character set_character_as_executive set_character_as_ruler
set_as_interest_group_leader set_character_immortal set_character_busy_and_immortal
set_temporary_event_immortality revoke_temporary_event_immortality replace_character_roles
set_career_length set_first_name set_last_name set_ideology change_character_culture
free_character_from_void set_popularity add_popularity remove_character_from_exile_pool""".split())
SAME = set("""if else else_if hidden_effect show_as_tooltip custom_tooltip on_created
effect after immediate option limit trigger AND OR NOT NOR NAND tooltip""".split())
CHAR_SELECT = re.compile(r'^(?:any|random|ordered|every)_(?:scope_)?character(?:_in_exile_pool)?$')
# Variable lists can hold characters: add_to_variable_list puts a handle in, *_in_list reads it back.
LIST_ADD = {'add_to_variable_list':'var:', 'add_to_global_variable_list':'gvar:', 'add_to_local_variable_list':'var:'}
LIST_ITER = re.compile(r'^(?:any|random|ordered|every)_in_(global_|local_)?list$')
SECTIONS = {'option','trigger','immediate','after','outcome','effect','on_created','possible',
            'on_monthly_pulse','on_weekly_pulse','on_yearly_pulse','when_taken'}

def handle(token, owner):
    hits = list(HANDLE.finditer(token or ''))
    if not hits or hits[-1].end() != len(token):
        return None
    prefix, name = hits[-1].groups()
    if prefix == 'scope':
        return f'charscope:{owner}/{name}'
    return ('gvar:' if prefix == 'global_var' else 'var:') + name


class Characters:
    def __init__(self, idx, loc):
        self.idx, self.loc = idx, loc
        self.links = []
        self.uses = []
        self.sinks = []
        self.seeds = set()
        self.calls = []
        self.script_calls = []
        self.owners = defaultdict(set)
        self.seen = set()

    def record(self, a, b, kind, rel, site):
        if not a or not b:
            return
        sf, off, ctx, flags = site
        signature = (a, b, rel, sf.root, sf.rel, off, ctx, flags)
        if signature in self.seen:
            return
        self.seen.add(signature)
        for key in (a,b):
            ty, name = key.split(':',1)
            self.idx.node(ty,name)
        self.idx.edges.append(dict(s=a,t=b,k=kind,rel=rel,ctx=ctx,file=sf.rel,
                                   root=sf.root,line=sf.line(off), **({'flags':list(flags)} if flags else {})))

    def identity(self, ident, sf, n):
        key = 'character:' + ident
        person = self.idx.node('character',ident,defined=True)
        site = dict(root=sf.root,file=sf.rel,line=sf.line(n.start),end=sf.line(n.end),how='character')
        if site not in person['sites']:
            person['sites'].append(site)
        names = [n.scalar(x) for x in ('first_name','last_name')]
        if names[0] and names[0] != 'culture':
            person['name'] = ' '.join(loc_resolve(self.loc,x) or x for x in names if x)
        self.seeds.add(key)
        return key

    def scan(self, owner, sf, blk):
        actor = 'charcontext:'+owner if owner.startswith(('seffect:','strigger:')) else None
        if owner.startswith('chartemplate:'):
            actor = self.identity(owner.split(':',1)[1],sf,blk)
            self.record(actor,owner,'struct','character_template',(sf,blk.start,'template',()))
        if owner.startswith(('event:','je:','button:','decision:')):
            nid = owner.split(':',1)[1]
            for suffix in ('','_reason','_desc','_status'):
                self.owners[nid + suffix].add(owner)
        self.walk(owner,sf,blk,actor,None,'definition',(),True)

    def walk(self, owner, sf, n, actor, prev, ctx, flags, definition=False):
        k, val = n.key or '', unquote(n.value) or ''
        if k in ('NOT','NOR','NAND'):
            flags = (*flags,'under_'+k)
        if k in SECTIONS:
            ctx = k
        if k in ('show_as_tooltip','event_outcome_effect_desc'):
            flags = (*flags,'tooltip_only')
        if n.children and any(ch.key in ('limit','trigger') and ch.scalar('always')=='no' for ch in n.children):
            flags = (*flags,'disabled')
        if k=='replace_character_roles':
            ctx = ctx+' / replace_character_roles'
        site = (sf,n.start,ctx,flags)
        parent_actor = actor
        selector = handle(k,owner)
        if selector and n.children is not None:
            actor = selector
        elif k == 'create_character':
            ident = (n.scalar('template') or n.scalar('character_template') or '').removeprefix('character_template:')
            if ident and IDENT.fullmatch(ident):
                actor = 'character:' + ident
                self.seeds.add(actor)
            elif ident:
                self.idx.unresolved.append(dict(src=owner,rtype='character',target=ident,file=sf.rel,
                                                line=sf.line(n.start),reason='dynamic character template'))
                actor = None
            else:
                alias = n.scalar('save_scope_as') or n.scalar('first_name') or 'anonymous'
                ident = f'{owner}/{alias}@{sf.rel.replace(" ","_")}:{sf.line(n.start)}.{n.start}'
                actor = self.identity(ident,sf,n)
            self.record(owner,actor,'call','create_character',site)
        elif (CHAR_SELECT.match(k) or k in ('ruler','heir','leader','executive')) and n.children is not None:
            limit = n.get('limit')
            template = (limit or n).scalar('has_template')
            if n.get('alternative_limit') or n.get('alternative_limit_2'):
                template = None
            if template and IDENT.fullmatch(template):
                actor = 'character:' + template
            else:
                # A runtime selector has its own identity, local to this site.
                actor = f'charselector:{owner}/{k}@{sf.rel}:{sf.line(n.start)}.{n.start}'
        elif LIST_ITER.match(k) and n.children is not None and IDENT.fullmatch(n.scalar('variable') or ''):
            # Each item of a variable list is the receiver inside the block.
            actor = ('gvar:' if LIST_ITER.match(k)[1]=='global_' else 'var:') + n.scalar('variable')
        elif k.upper() == 'PREV':
            actor = prev
        elif not definition and n.children is not None and k not in SAME and k not in ('traits','replace_character_roles','add','remove','set_global_variable','set_variable','add_modifier','has_modifier','remove_modifier','any_character_role','commander_usage') and k not in OPERATIONS and k not in LIST_ADD:
            actor = None

        if not definition:
            for typ in ('seffect','strigger'):
                callee = typ+':'+k
                if callee in self.idx.defs:
                    self.calls.append((owner,callee,site))
                    self.script_calls.append((owner,callee,site))
                    if actor:
                        self.links.append((actor,'charcontext:'+callee,'scripted_character_receiver',site))
            if actor and actor.startswith('charselector:') and (CHAR_SELECT.match(k) or k in ('ruler','leader','heir','executive')):
                self.record(owner,actor,'struct','select_character',site)
                for filtblock in [n.get('limit') or n, *n.all('alternative_limit')]:
                    def conditions(block, family):
                        for ch in block.children or []:
                            if ch.key=='has_template' and ch.value and IDENT.fullmatch(unquote(ch.value)):
                                self.record(actor,'character:'+unquote(ch.value),'cond','candidate_template',
                                            (sf,ch.start,ctx,(*flags,*family)))
                            elif ch.key in ('AND','OR','NOT','NAND','NOR'):
                                conditions(ch,(*family,'under_'+ch.key))
                    conditions(filtblock,('fallback',) if filtblock.key=='alternative_limit' else ())
                filt = n.get('limit') or n
                for ch in filt.children or []:
                    if ch.key=='has_variable' and ch.value:
                        self.record(actor,'var:'+unquote(ch.value),'cond','filter_character_flag',
                                    (sf,ch.start,ctx,flags))
            if owner.startswith('chartemplate:') and k.endswith('_usage'):
                self.record('character:'+owner.split(':',1)[1],'charstate:'+k,'struct',k,site)
            for token in (k,val):
                for segment in HANDLE.finditer(token):
                    ref = handle(segment[1]+':'+segment[2],owner)
                    self.uses.append((owner,ref,'character_handle',site))
                for match in re.finditer(r'(?:^|\.)character_template:([\w-]+)',token):
                    self.record(owner,'character:'+match[1],'cond','character_template',site)
            if val and (k in TEMPLATE or 'chartemplate:'+val in self.idx.defs):
                if k != 'template' or 'chartemplate:'+val in self.idx.defs:
                    raw = val.removeprefix('character_template:')
                    if IDENT.fullmatch(raw) and (k in TEMPLATE or 'chartemplate:'+raw in self.idx.defs):
                        self.record(owner,'character:'+raw,'cond' if k not in ('template','character_template') else 'struct',k,site)
            if val in self.loc and (owner.startswith(('event:','je:','button:','decision:','customloc:'))
                                    or k in ('text','custom_tooltip','desc','title')):
                self.owners[val].add(owner)

        if k in ('save_scope_as','save_temporary_scope_as') and actor and val:
            self.links.append((actor,handle('scope:'+val,owner),'save_scope_as',site))
        if k in ('set_variable','set_global_variable'):
            slot_name = n.scalar('name') or val
            slot = ('gvar:' if k=='set_global_variable' else 'var:') + slot_name
            if not IDENT.fullmatch(slot_name):
                slot = None
            value = n.scalar('value') or ''
            source = {'this':actor,'prev':prev}.get(value.lower()) or handle(value,owner)
            if source and slot:
                self.links.append((source,slot,k,site))
            elif actor and slot and not value:
                self.sinks.append((actor,slot,'character_flag',site))
        if k in LIST_ADD and n.children is not None:
            list_name = n.scalar('name') or ''
            target = n.scalar('target') or ''
            source = {'this':actor,'prev':prev}.get(target.lower()) or handle(target,owner)
            if source and IDENT.fullmatch(list_name):
                self.links.append((source,LIST_ADD[k]+list_name,k,site))
        if actor:
            target = None
            if k in ('is_character_alive','is_in_exile_pool','is_immortal','is_ruler_of_own_country'):
                target = 'charstate:'+k+'='+val
            elif k=='remove_all' and ctx.endswith('replace_character_roles'):
                target = 'charstate:remove_all_roles='+val
            elif k in OPERATIONS and (not n.get('CHARACTER') or k!='revoke_temporary_event_immortality'):
                target = 'charstate:'+k+('='+val if val else '')
            elif k in POSITIONS and val=='yes':
                role = POSITIONS[k]
                target = 'charrole:character_role_'+role
            elif k in ('role','add_character_role','remove_character_role','has_role','has_role_of_type','is_character_role') and val:
                target = 'charrole:'+(val if val.startswith('character_role_') else 'character_role_'+val)
            elif k in ('add_trait','remove_trait','has_trait') and val:
                target = 'trait:'+val
            elif k in ('interest_group','ideology') and val:
                candidate = ('ig:' if k=='interest_group' else 'ideology:')+val.split(':')[-1]
                if candidate in self.idx.defs:
                    target = candidate
            elif k in ('add_modifier','remove_modifier','has_modifier'):
                name = n.scalar('name') or val
                if name and IDENT.fullmatch(name):
                    target = 'modifier:'+name
            if target:
                self.sinks.append((actor,target,k,site))
            if k in ('traits','replace_character_roles'):
                groups = [(n,'trait:','traits')] if k=='traits' else [(ch,'charrole:',ch.key) for ch in n.children or [] if ch.key in ('add','remove')]
                for group, prefix, rel in groups:
                    for ch in group.children or []:
                        value = unquote(ch.value)
                        if not ch.key and value:
                            if prefix=='charrole:' and not value.startswith('character_role_'):
                                value = 'character_role_'+value
                            self.sinks.append((actor,prefix+value,rel,(sf,ch.start,ctx,flags)))
        # Explicit character arguments to a scope-changing helper.
        if k in ('revoke_temporary_event_immortality','set_temporary_event_immortality'):
            ref = handle(n.scalar('CHARACTER'),owner)
            if ref:
                self.sinks.append((ref,'charstate:'+k,k,site))
        if owner.startswith('chartemplate:') and k=='is_company_type' and val.startswith('company_type:'):
            self.sinks.append(('character:'+owner.split(':',1)[1],'company:'+val.split(':',1)[1],k,site))
        if k in ('trigger_event',):
            eid = val or n.scalar('id')
            if eid:
                self.calls.append((owner,'event:'+eid,site))
        # prev changes on scope transitions, including ROOT/owner, not on control blocks.
        outer = parent_actor if (actor!=parent_actor or k.lower() in ('root','owner')) else prev
        for child in n.children or []:
            self.walk(owner,sf,child,actor,outer,ctx,flags)

    def finish(self, locsrc, loclayers):
        outgoing = defaultdict(list)
        for a,b,rel,site in self.links:
            outgoing[a].append((b,rel,site))
        # Only transport a local name over an explicit invocation when the callee reads it.
        reads = defaultdict(set)
        for owner,slot,_,_ in self.uses:
            if slot.startswith('charscope:'):
                reads[owner].add(slot.rsplit('/',1)[1])
        for caller,callee,site in self.calls:
            for name in reads[callee]:
                outgoing[handle('scope:'+name,caller)].append((handle('scope:'+name,callee),'event_scope_argument',site))
        # An effect can save a scope that its caller subsequently consumes.
        # Qualify both ends and require a real call and corresponding write.
        saved = defaultdict(set)
        for _,slot,rel,_ in self.links:
            if rel=='save_scope_as' and slot:
                local_owner,name = slot[len('charscope:'):].rsplit('/',1)
                saved[local_owner].add(name)
        for caller,callee,site in self.script_calls:
            for name in saved[callee] & reads[caller]:
                outgoing[handle('scope:'+name,callee)].append((handle('scope:'+name,caller),'script_scope_result',site))
        # Keep runtime selector nodes when a character operation or explicit alias uses them.
        seeds = self.seeds | {a for a in outgoing if a.startswith('charselector:')}
        seeds.update(a for a,_,_,_ in self.sinks if a.startswith('charselector:'))
        # A typed operation establishes a character handle even when an engine/UI
        # entry point supplied it. This does not identify the occupant.
        for actor,target,rel,_ in self.sinks:
            if actor.startswith(('charscope:','var:','gvar:')) and target.startswith(('charstate:','charrole:','trait:')):
                seeds.add(actor)
        # In a character-valued assignment either end constrains the other.
        upstream = defaultdict(set)
        for source, bindings in outgoing.items():
            for slot,rel,_ in bindings:
                if rel in ('set_variable','set_global_variable','save_scope_as','event_scope_argument','script_scope_result',*LIST_ADD):
                    upstream[slot].add(source)
        known = set(seeds)
        queue = deque(sorted(seeds))
        while queue:
            actor = queue.popleft()
            for source in upstream.get(actor,()):
                if source not in known:
                    known.add(source)
                    queue.append(source)
            for slot,rel,site in outgoing[actor]:
                self.record(actor,slot,'struct',rel,site)
                if slot not in known:
                    known.add(slot)
                    queue.append(slot)
        for owner,slot,rel,site in self.uses:
            if slot in known:
                self.record(owner,slot,'cond',rel,site)
        for actor,target,rel,site in self.sinks:
            if actor in known:
                self.record(actor,target,'cond' if rel.startswith(('has_', 'is_character_role','is_character_alive','is_in_exile_pool','is_immortal','is_ruler_of_own_country')) else 'struct',rel,site)
        for key,value in self.loc.items():
            if not LOC_HANDLE.search(value):
                continue
            locowners = self.owners.get(key,())
            located = set()
            for m in LOC_HANDLE.finditer(value):
                name = m[1]
                if m[0].lower().startswith('scope.'):
                    slots = [handle('scope:'+name,o) for o in locowners]
                else:
                    slots = [('gvar:' if m[0].lower().startswith('getglobal') else 'var:')+name]
                for slot in set(slots) & known:
                    if (slot,m[0]) in located:
                        continue
                    located.add((slot,m[0]))
                    file,line = locsrc[key].rsplit(':',1)
                    idxnode = self.idx.node('charloc',key,defined=True)
                    site = dict(root=loclayers[key],file=file,line=int(line),end=int(line),how='localization')
                    if not idxnode['sites']:
                        idxnode['sites'].append(site)
                    self.idx.edges.append(dict(s=idxnode['key'],t=slot,k='cond',rel='display_character',ctx=m[0],
                                               root=site['root'],file=file,line=int(line)))

def add_characters(idx,loc,locsrc,loclayers):
    scan = Characters(idx,loc)
    for owner,definitions in idx.defs.items():
        for sf,blk in definitions:
            scan.scan(owner,sf,blk)
    scan.finish(locsrc,loclayers)
