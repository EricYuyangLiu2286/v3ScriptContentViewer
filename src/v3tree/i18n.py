"""All user-facing text in one table: {key: (zh, en)}.

The index stores context labels in the language it was built with; reports and
web pages use the same table. Add a key here instead of writing text inline.
"""
from __future__ import annotations

LANG = 'zh'

S = {
    # ---- node types
    'type.je': ('日志', 'Journal entry'),
    'type.button': ('按钮', 'Button'),
    'type.bar': ('进度条', 'Progress bar'),
    'type.event': ('事件', 'Event'),
    'type.decision': ('决议', 'Decision'),
    'type.law': ('法律', 'Law'),
    'type.dp': ('外交博弈', 'Diplomatic play'),
    'type.wargoal': ('战争目标', 'War goal'),
    'type.modifier': ('修正', 'Modifier'),
    'type.var': ('变量/flag', 'Variable/flag'),
    'type.gvar': ('全局变量/flag', 'Global variable/flag'),
    'type.onaction': ('on_action', 'on_action'),
    'type.seffect': ('scripted effect', 'Scripted effect'),
    'type.strigger': ('scripted trigger', 'Scripted trigger'),
    'type.svalue': ('script value', 'Script value'),
    'type.tag': ('国家/tag', 'Country/tag'),
    'type.chartemplate': ('人物模板', 'Character template'),
    'type.culture': ('文化', 'Culture'),
    'type.customloc': ('自定义本地化', 'Custom localization'),
    'type.movement': ('政治运动', 'Political movement'),
    'type.diplaction': ('外交行动', 'Diplomatic action'),
    'type.history': ('开局历史', 'Start history'),
    'type.pop': ('人口对象', 'Pop object'),
    'type.dynname': ('动态国名', 'Dynamic country name'),
    'type.govtype': ('政体类型', 'Government type'),
    'type.srule': ('scripted rule', 'Scripted rule'),
    'type.subjtype': ('附属类型', 'Subject type'),
    'type.charinter': ('人物互动', 'Character interaction'),
    'type.formation': ('国家成立', 'Country formation'),
    'type.objective': ('开局目标', 'Objective'),
    'type.aistrat': ('AI 策略', 'AI strategy'),
    'type.treaty': ('条约条款', 'Treaty article'),
    'type.pbprinciple': ('集团原则', 'Power bloc principle'),
    'type.ideology': ('意识形态', 'Ideology'),
    'type.socialclass': ('社会阶层', 'Social class'),
    'type.socialhier': ('社会阶序', 'Social hierarchy'),
    'type.lawgroup': ('法律组', 'Law group'),
    'type.party': ('政党', 'Party'),
    'type.movesupport': ('运动支持度', 'Movement pop support'),
    'type.pbname': ('集团名称', 'Power bloc name'),
    'type.flagdef': ('旗帜定义', 'Flag definition'),
    'type.creation': ('可释放国家', 'Releasable country'),

    # ---- context labels (where in a definition a reference sits)
    'ctx.immediate': ('开始时', 'immediate'),
    'ctx.on_monthly_pulse': ('每月脉冲', 'monthly pulse'),
    'ctx.on_weekly_pulse': ('每周脉冲', 'weekly pulse'),
    'ctx.on_yearly_pulse': ('每年脉冲', 'yearly pulse'),
    'ctx.is_shown_when_inactive': ('显示条件', 'shown when'),
    'ctx.possible': ('开启条件', 'possible'),
    'ctx.is_shown': ('显示条件', 'shown when'),
    'ctx.visible': ('可见条件', 'visible when'),
    'ctx.trigger': ('条件', 'trigger'),
    'ctx.after': ('after', 'after'),
    'ctx.when_taken': ('决议效果', 'when taken'),
    'ctx.on_complete': ('on_complete', 'on_complete'),
    'ctx.on_fail': ('on_fail', 'on_fail'),
    'ctx.on_timeout': ('on_timeout', 'on_timeout'),
    'ctx.on_invalid': ('on_invalid', 'on_invalid'),
    'ctx.complete': ('完成条件', 'complete when'),
    'ctx.fail': ('失败条件', 'fail when'),
    'ctx.invalid': ('失效条件', 'invalid when'),
    'ctx.status_desc': ('状态文字', 'status text'),
    'ctx.effect': ('效果', 'effect'),
    'ctx.should_be_involved': ('参与条件', 'involved when'),
    'ctx.should_show_when_not_involved': ('旁观显示条件', 'shown to others when'),
    'ctx.modifiers_while_active': ('生效期间修正', 'modifiers while active'),
    'ctx.ai_chance': ('AI权重', 'AI weight'),
    'ctx.ai_will_do': ('AI权重', 'AI weight'),
    'ctx.can_enact': ('可颁布条件', 'can enact'),
    'ctx.is_visible': ('可见条件', 'visible when'),
    'ctx.on_enact': ('颁布时', 'on enact'),
    'ctx.on_activate': ('生效时', 'on activate'),
    'ctx.on_deactivate': ('失效时', 'on deactivate'),
    'ctx.start_value': ('进度起始值', 'bar start value'),
    'ctx.monthly_progress': ('进度月推进', 'bar monthly progress'),
    'ctx.weekly_progress': ('进度周推进', 'bar weekly progress'),
    'ctx.potential': ('前提条件', 'potential'),
    'ctx.allow': ('允许条件', 'allow'),
    'ctx.events': ('on_action 事件', 'on_action events'),
    'ctx.random_events': ('on_action 随机事件', 'on_action random events'),
    'ctx.on_actions': ('链式 on_action', 'chained on_action'),
    'ctx.desc': ('描述条件', 'description trigger'),
    'ctx.title': ('标题条件', 'title trigger'),
    'ctx.cancel_if_invalid': ('cancel_if_invalid', 'cancel_if_invalid'),
    'ctx.on_created': ('创建时', 'on created'),
    'ctx.button_effect': ('按钮效果', 'button effect'),
    'ctx.onaction_effect': ('on_action 效果', 'on_action effect'),
    'ctx.event_immediate': ('immediate', 'immediate'),
    'ctx.seffect_body': ('效果体', 'effect body'),
    'ctx.history_body': ('开局历史', 'start history'),
    'ctx.strigger_body': ('条件体', 'trigger body'),
    'ctx.svalue_body': ('数值体', 'value body'),
    'ctx.customloc_body': ('文本条件', 'text trigger'),
    'ctx.template_body': ('人物模板', 'character template'),
    'ctx.dynname_body': ('动态国名条件', 'dynamic name trigger'),
    'ctx.button': ('按钮', 'button'),
    'ctx.bar': ('进度条', 'progress bar'),
    'ctx.outcome': ('结局{n}({kind})·{part}', 'outcome {n} ({kind}) · {part}'),
    'ctx.outcome.trigger': ('条件', 'trigger'),
    'ctx.outcome.effect': ('效果', 'effect'),
    'ctx.option': ('选项{n}', 'option {n}'),
    'ctx.option_trigger': ('选项{n}·条件', 'option {n} · trigger'),
    'ctx.random_weight': ('{ctx} 随机 {w}/{total}', '{ctx} random {w}/{total}'),
    'ctx.random_branch': ('{ctx} 随机分支 {w}', '{ctx} random branch {w}'),
    'ctx.random_chance': ('{ctx} 随机 {ch}%', '{ctx} random {ch}%'),
    'ctx.delay': ('延迟{n}{unit}', 'after {n} {unit}'),
    'unit.days': ('天', 'days'), 'unit.weeks': ('周', 'weeks'), 'unit.months': ('月', 'months'), 'unit.years': ('年', 'years'),
    'ctx.via_param': ('经 {callee} 参数', 'via parameter of {callee}'),
    'outcome.invalid': ('失效', 'invalid'),
    'outcome.timeout': ('超时', 'timeout'),
    'outcome.failure': ('失败', 'failure'),
    'outcome.success': ('完成', 'success'),
    'site.replaced': ('（被替换）', ' (replaced)'),
    'site.merged': ('合并', 'merged'),
    'name.dynname_suffix': ('·动态国名', ' · dynamic name'),

    # ---- index diagnostics
    'unres.dynamic_param_outside': ('动态参数且不在 scripted effect/trigger 内', 'parameter outside a scripted effect/trigger'),
    'unres.dynamic_target': ('动态目标（scope/变量/链式），无法静态解析', 'dynamic target (scope / variable / chain), not statically resolvable'),
    'unres.param_no_caller': ('参数化引用，未找到给出该参数的调用点', 'parameterised reference; no call site supplies the parameter'),
    'unres.param_key_no_caller': ('参数化键名，未找到给出该参数、且解析为 scripted effect/trigger 的调用点',
                                  'parameterised key; no call site supplies it as a scripted effect/trigger'),
    'dis.event': ('trigger = { always = no }', 'trigger = { always = no }'),
    'dis.decision': ('is_shown/possible = { always = no }', 'is_shown/possible = { always = no }'),
    'dis.button': ('visible/possible = { always = no }', 'visible/possible = { always = no }'),
    'dis.je': ('possible = { always = no }，且没有 add_journal_entry 入口', 'possible = { always = no } and nothing adds it'),

    # ---- verdicts
    'v.in': ('同主题', 'in theme'),
    'v.boundary': ('边界', 'boundary'),
    'v.out': ('无关', 'unrelated'),
    'v.unjudged': ('待定', 'undecided'),
    'v.stopped': ('停止规则', 'stop rule'),
    'v.root': ('根节点', 'root'),
    'v.unjudged_boundary': ('未判定（边界节点不展开）', 'not judged (boundary nodes are not expanded)'),
    'v.unjudged_plain': ('未判定', 'not judged'),
}


from .i18n_ui import UI as _UI  # noqa: E402
S.update(_UI)


def set_lang(lang: str):
    global LANG
    LANG = 'en' if str(lang).lower().startswith('en') else 'zh'


def T(key: str, **kw) -> str:
    pair = S.get(key)
    if pair is None:
        return key
    s = pair[0] if LANG == 'zh' else pair[1]
    return s.format(**kw) if kw else s


def type_name(t: str) -> str:
    return T(f'type.{t}') if f'type.{t}' in S else t


def table(lang: str | None = None) -> dict:
    """Flat {key: text} for the web pages."""
    i = 0 if (lang or LANG) == 'zh' else 1
    return {k: v[i] for k, v in S.items()}
