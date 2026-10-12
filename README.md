# Browser Comment Research Skill

一个用于动态网页评论研究的可调用 Codex Skill。研究者在普通浏览器中使用自己的账号登录，程序只读取正常页面及其正常加载的评论响应，记录有限候选池，再进行可复现抽样。

支持已登记视频的哔哩哔哩（BILI）、抖音（DY）、微博（WB）、小红书（XHS）页面适配；提供离线演示、冻结输入、确定性抽样、CSV、可选 Excel、缺口审计和哈希核验。**这是有限采样工具，不能声称获取每个视频全部评论。** 视频发现由调用 Skill 的助手按照工作流辅助登记；回复上下文目前需正常页面人工辅助记录，不在自动采集脚本中。

## 安装 Skill

在本仓库 Releases 下载发布 ZIP，解压后得到 `browser-comment-research` 文件夹。在该文件夹运行：

```sh
python scripts/install_skill.py
```

默认安装至 `~/.codex/skills/browser-comment-research`，Windows 使用 Python 对应的用户主目录。也可用 `--destination <你的skills目录>`。拒绝覆盖同名旧版。安装后重新打开 Codex 会话，使其发现 Skill；调用：

> 使用 $browser-comment-research，先做离线演示，再根据我的案例与视频清单建立可复现采集项目。

也可以只下载代码，直接使用命令行，不依赖 Codex。Python 3.12 或以上；真实采集还需要本机 Google Chrome 和 Scrapling 浏览器依赖。其他助手是否支持自动发现此 Skill 取决于其自身规范。

## 先试离线演示

下面路径 `demo-project` 必须尚不存在；所有演示视频和评论都是合成的。

```sh
python scripts/research.py demo --project demo-project
python scripts/research.py verify --project demo-project
```

演示只需要 Python 标准库，不联网、不登录。输出在项目 `outputs/`。

## 真实采集

```sh
python -m venv .venv
# 激活虚拟环境后执行；Windows 为 .venv\Scripts\activate
pip install -r requirements.txt
scrapling install
python scripts/research.py init --project my-research
```

按 [说明书](references/manual.md) 修改 `my-research/inputs/plan.json`、`config.json`、`access.json`。示例中的 `example.invalid` 不能用于真实采集。账号登录不等于具有自动化访问许可，须核实相关规则与授权依据。

```sh
python scripts/research.py login --project my-research --platform BILI
python scripts/research.py collect --project my-research --platform BILI
python scripts/research.py summarize --project my-research
python scripts/research.py verify --project my-research
pip install -r requirements-excel.txt
python scripts/export_xlsx.py --project my-research
```

登录由研究者本人在弹出的普通 Chrome 完成。不会读取或复制 Edge 的登录资料。默认每流最多50候选位置，H抽10条、T按可及时间三段抽3/4/3条；没有原生时间序时标记默认流51–100位置的延续，不称为“最新”。缺口不补齐、不挪配额；H/T重复身份只保留一份正文、保留两份成员资格。K关键词补充另列，关键词命中不等于理论类别，否定表达同样保留。

## 文件与复现

- `SKILL.md`：调用规则；`agents/openai.yaml`：界面元数据。
- `scripts/`：采集、抽样、核验、安装和 Excel 导出代码。
- `references/workflow.md`：从研究范围到归档的完整流程。
- `references/manual.md`：输入结构、命令、故障与限制。
- `examples/`：完全合成、默认未获访问批准的配置。
- `tests/`：离线回归测试；GitHub Actions 自动运行。

项目保留 `inputs/`、`inputs.sha256.json`、`evidence/<任务>/capture.json`、`outputs/result.json`、`audit.json`、`comments.csv`、可选 `comments.xlsx`。重跑冻结候选池可得到相同抽样；动态网页内容会变化，再次在线采集不保证同一评论集合。真实数据和 `.private/` 不应放进公开仓库。

## 测试范围与限制

适配器来自实际四平台项目使用过的方法，公开版已移除固定案例、电脑路径与个人数据，改为独立参数输入。发布验证覆盖语法、合成抽样、冻结输入、哈希核验、安装和 Excel 身份/公式/日期保护；**公开重构版本未重新登录四个平台进行在线验收**。首次实际使用务必每个平台先试一个视频。页面选择器、正常响应字段和登录流程可能变化；微博需明确提供原生帖子数字 ID。遇到验证码、限流或登录要求停止，不自动绕过。图片无文字时保留类型，但不下载图片、不做 OCR。未知时间不进入期内抽样。跨流同身份正文或日期冲突报错，须保留原始观察并人工核验，不能静默覆盖。

默认规则适用于探索性内容分析，不是概率总体抽样，不可据此推断平台总体比例、证明理论结构或替代人工编码与信度检验。

## 开源与参与

MIT 许可，见 [LICENSE](LICENSE)。问题或适配器修复请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。隐私与漏洞报告见 [SECURITY.md](SECURITY.md)。版本历史见 [CHANGELOG.md](CHANGELOG.md)。使用代码请在研究方法中记录版本、提交号、配置和访问时间。
