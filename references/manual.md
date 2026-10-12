# 说明书

## 输入

`examples/plan.json` 示范三张逻辑表：

- cases：event_id、category、queries（3条正常检索词）。
- videos：event_id、platform、video_id、url、title、author、published_at、comment_count、selection_rank。元数据需正常页面核实。
- units：每个实际采集任务的unit_id、event_id、category、platform、video_id、url、title。必须对应cases和videos。任务ID只能包含字母数字、下划线、短横线；不可使用路径字符。微博另外在unit中填native_post_id（帖子原生数字ID，不是地址栏短码）。

平台缩写 BILI/DY/WB/XHS。URL仅正常对应平台HTTPS网址；不得填写内网或文件地址。小红书通过cases.queries在正常搜索页面定位相同video_id卡片，再核实详情身份；可用collect的 --query 1/2/3指定冻结查询词。已登录未必能搜到旧视频，找不到须留缺口。

config：seed固定字符串；comment_window两端带+08:00；H_sample、T_sample_by_accessible_time_tercile、supplement_keywords、supplement_per_video_max可在冻结前修改。在线适配器当前positions_per_stream固定50；停止预算480秒与视频间10秒在代码中明确。其他描述字段不会改变采集实现。

access：每平台approved真实布尔值；basis为已核实访问依据，robots_review为相关路径规则核查与结论，reviewed_at为24小时内ISO带时区时间。空/过期拒绝采集。该登记是审查证据，不是由软件自动判定合法性；若规则不允许，应停止。

## 命令

所有命令在仓库根目录执行，项目目录在仓库外，路径含空格时用引号。

- init：复制输入模板，目标必须新建。
- demo：生成纯合成证据并抽样，目标必须新建。
- login：指定platform，让本人在普通Chrome中登录；完成后终端回车。
- collect：指定platform；可选--events若干案例ID、--query 1/2/3。拒绝覆盖已有任务证据。
- summarize：对冻结证据重算中性/K抽样，输出JSON/CSV与任务审计。
- verify：核对冻结输入、原始证据SHA256，并对抽样重算后字节比较。
- export_xlsx.py：可选依赖openpyxl；生成评论及任务审计两个工作表。ID以字符串存储；原始文本不会作为公式；北京时间以数值墙上时间写入，无8小时偏移。人工编码列为空。
- install_skill.py：复制至用户skills目录，同名拒绝覆盖。

## 常见问题

缺口不等于漏抓全量：本工具只读取有限位置；预算、日期和可及池可造成预设配额不足。达到配额也不等于获取全部评论。

零条不判定无评论：可能目标未定位、登录、响应结构变化、微博缺native_post_id、未知时间或页面未加载。查capture.json中的status、stop_reason、actions、missing_native_id_n、error、sample_error与streams。

版本冲突：同一原生评论在两个流的日期或内容变化会被sampler拒绝；原始观察保留，人工核实后新建修订版证据并记录修改，不编辑原始证据冒充原始。

日期：原生秒/毫秒时间或微博英文created_at转北京时间；B站公开日期只有日粒度时用该日完整上下界；未知日期明确排除，不凭猜测日期补入。

保密：截图可能有账号信息；分享前人工审核。不要提交/private、cookie、令牌、浏览器profile、真实评论、真实视频计划或原始页面响应。错误报告只提供脱敏的字段结构和合成最小复现。

## 可复现的边界

冻结输入+冻结候选池+相同程序版本可以复现抽样。重新访问平台的结果会因排序、删评、账号、地域与时间变化。软件版本、浏览器版本和登录环境应写入研究日志；不能把公开示例测试当作实时平台可用性保证。
