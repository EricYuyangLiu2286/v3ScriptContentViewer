# 配置

v3tree 只读一个 JSON 文件，默认在 `<仓库>/config/local.json`（不提交到 git）。每个命令都接受 `--config 路径`，可以一套 MOD 组合用一个文件。

三种生成方式：

- `python run.py init` 依次询问：界面语言、游戏目录（会给出经 Steam 找到的路径）、是否导入启动器游戏集（默认否）、逐行输入 MOD 目录、本地化语言、输出目录。
- `python run.py init --game "<目录>" --mod "<MOD 1>" --mod "<MOD 2>" --languages simp_chinese,english --ui zh [--output <目录>]` 不提问（脚本和 AI 用这个）。`--playset` 改从启动器读取 MOD，替代 `--mod`；`--game ""` 表示不用原版。
- 网页“设置”，或按下面的格式手写。

`init` 会自动检查，有错误的配置不会保存。默认输出目录是 `<仓库>/output`。

```json
{
  "schema": 1,
  "game": { "path": "C:/Program Files (x86)/Steam/steamapps/common/Victoria 3" },
  "mods": [
    { "path": "C:/.../workshop/content/529340/3385002128", "name": "Community Mod Framework" },
    { "path": "C:/Users/me/Documents/Paradox Interactive/Victoria 3/mod/My Mod", "name": "My Mod" }
  ],
  "load_order_source": "manual",
  "languages": ["simp_chinese", "english"],
  "ui_language": "zh",
  "output_dir": "C:/Users/me/v3tree-output",
  "script_docs_dir": null,
  "ignore": ["**/_backup*/**"],
  "extra_folders": {},
  "detected": {}
}
```

| 字段 | 含义 |
|---|---|
| `game.path` | 游戏安装目录，或其下的 `game` 子目录。可以留空，但 `game` 与 `mods` 不能都为空。 |
| `mods` | MOD 目录，**按加载顺序：先加载的在前，后加载的覆盖先加载的。** 可以为空。 |
| `load_order_source` | `launcher`（从启动器读取）或 `manual`（手工排序）。手工调整后变为 `manual`。 |
| `languages` | 取名称用的本地化目录，靠前的优先，例如 `["simp_chinese", "english"]`。 |
| `ui_language` | `zh` 或 `en`：界面、报告，以及写进索引的上下文标签。改后请重建索引。 |
| `output_dir` | 索引和用例的存放位置。 |
| `script_docs_dir` | 放 `effects.log`、`triggers.log`、`event_targets.log` 的目录。留空则到 `<文档>/Paradox Interactive/Victoria 3/docs` 找。 |
| `ignore` | 不读取的路径（相对各 MOD 目录的通配符）。 |
| `extra_folders` | `{"common/新目录": "类型名"}`，游戏更新新增数据库目录时，不改代码也能补进索引。 |
| `detected` | 由 `doctor` 写入（游戏版本、Steam 构建号），不要手改。 |

## 加载顺序

- **从启动器读取：** 启动器把当前游戏集已启用的 MOD 按顺序写在 `<文档>/Paradox Interactive/Victoria 3/content_load.json` 的 `enabledMods` 里。`init` 和网页“设置”可以导入。
- **未证实：** 这个列表顺序就是加载顺序、后加载的覆盖先加载的。`doctor` 会列出顺序请你确认。自己验证的办法：做两个小 MOD，用不同内容定义同一个静态修正，看游戏里生效的是哪个。
- 没有这个文件或顺序不对时，手工排序。

## 启动检查（`doctor`）

退出码：0 = 全部通过；1 = 有提示，可以继续；2 = 有错误，不能继续。

| 检查项 | 结果 |
|---|---|
| 至少一个路径 | 游戏和 MOD 都没填时报错。 |
| 游戏目录 | 下面没有 `game/common` 时报错。版本取自 `launcher/launcher-settings.json`。 |
| 每个 MOD | 从 `.metadata/metadata.json` 读名称和支持的版本；与游戏版本不同时提示；既没有 metadata 也没有 `common/`、`events/`、`localization/` 时报错。 |
| 没填游戏目录 | 提示：引用原版的内容会显示为“未定义”。 |
| 加载顺序 | 有两个以上 MOD 时提示确认。 |
| 接口清单 | 缺失时提示：“未识别键”检查跳过，抽边不受影响。在游戏控制台输入 `script_docs` 可以生成。 |
| 语言 | 某语言目录在所有层都不存在时提示。 |
| 输出目录 | 不可写时报错。 |
