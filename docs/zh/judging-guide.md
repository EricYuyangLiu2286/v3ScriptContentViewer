# 判定指南

索引只说明什么和什么相连。一张图还要知道哪些属于主题（例如“X 内战及其直接后果”）。这是判断，由人或 AI 来做，并写下理由。

## 三种结论

| 结论 | 含义 | 图上 |
|---|---|---|
| `in` | 属于主题，接着列出它的邻居。 | 画出并展开 |
| `boundary` | 另一个系统，但与主题直接相连（`@` 后写系统名）。 | 虚线框，不展开 |
| `out` | 无关：通用工具、参数、顺带的引用。 | 不画，记入报告和侧栏 |

粗略的判断法：去掉这个主题，这个节点还有没有用处？没有了 → `in`。它属于主题碰到的另一个系统？→ `boundary`。它是通用工具或只是传过去的值？→ `out`。

## 判定文件

每条一行，`//` 开头是注释。同一个 KEY 以后出现的为准；逐项判定优先于规则；多条规则取第一条匹配的。

```
in event:my_events.3 # 开战时触发
boundary je:my_other_je @日本政局 # 读取本主题的战争标记，属另一系统
out strigger:is_at_war_generic # 通用工具
rule R1 in type=event file_regex=^events/my_war_events\.txt$ # 战争事件文件里的事件都属于本主题
rule R2 boundary @国家 type=tag # 国家画出、不展开
soft yes seffect:a_moves_pops|seffect:b_reads_pops|pop:my_culture_trigger # 两边处理的是同一批人口
soft no *|*|law:* # 法律被大量系统共用
```

规则条件：`type=a,b`、`id_regex` 匹配不带前缀的 id，`key_regex` 匹配完整 KEY（如 `seffect:x`），`file_regex=…`（任一定义位置）、`root=game|mod|mod2`（定义来自哪一层；`mod` 表示任一 MOD 层）、`undefined=1`。

节点类型（每个 KEY 冒号前的前缀，用于 `type=`）：`je` 日志、`event` 事件、`decision` 决议、`button` 按钮、`bar` 进度条、`law` 法律、`dp` 外交博弈、`wargoal` 战争目标、`modifier` 修正、`var` 变量、`gvar` 全局变量、`onaction`、`seffect` scripted effect、`strigger` scripted trigger、`svalue` script value、`tag` 国家、`chartemplate` 人物模板、`culture` 文化、`pop` 人口对象、`customloc`、`history` 开局历史、`movement` 政治运动、`govtype` 政体、`dynname` 动态国名、`party` 政党、`ideology` 意识形态、`lawgroup` 法律组、`socialclass`、`socialhier`、`formation`、`treaty`、`subjtype`、`charinter`、`diplaction`、`objective`、`aistrat`、`srule`、`pbprinciple`、`pbname`、`flagdef`、`creation`、`movesupport`。

系统名里的 `_` 显示为空格。

## 软边

软边指“一方写某个对象，另一方读它”，例如两边都迁移同一批人口，或者一处设全局变量、另一个系统读取。共享对象**不属于同主题**时才列候选：判为 `boundary` 或 `out` 的对象，以及人口对象。（同主题对象会被展开，它的读写方本来就会作为普通邻居出现。）边界对象虽然画在图上，但它的其他读写方在图外，所以仍列候选。只确认对主题有意义的，候选清单里已给出两端出处。

写法：`soft yes|no 写方|读方|对象 # 理由`。先写方、后读方。`*` 可以代替写方、读方或两者；对象可以是整个类型：`soft no *|*|law:*`。最具体的一条生效（完整一对 → 单边通配 → `*|*|对象` → `*|*|类型:*`）。

图上，经同一个已画出对象的多对软边，会合并成外部节点与该对象之间的一条虚线。

## 常见错误

- **按定义所在文件判断归属。** 看它做什么、被谁开启。定义在别的功能文件里的改革 JE，仍可能属于你的主题。
- **把枢纽判成同主题。** 被几十个系统读取的变量或条件会把它们全部牵进来。判成 `boundary`，在侧栏里看它的读取方。
- **把通用法律、文化判成同主题。** 它们被引用成百上千次，多数只是参数。
- **`show_as_tooltip`。** 里面的效果只显示、不执行。边带有 `tooltip_only` 标记，报告会检查它是否在别处真正执行。
- **同名不同对象。** 变量与人物模板、事件命名空间与变量可能同名。反向检查已考虑这一点，判定时也要留意。

## 索引漏抓

报告的反向检查会列出同主题 id 在 MOD 脚本原文中、无法由任何边解释的出现。每一处要么是索引漏抓（修索引后重建），要么是同名的别的东西。不要在判定文件里手工补边来掩盖漏抓。
