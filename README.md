# stock-analyze

当前项目已经改成纯 Python 版，不再依赖 Java、Maven、Spring Boot。

保留能力：

- `akshare` 拉取股票数据
- 每 1 分钟执行一次定时任务
- 发送企业微信消息
- 提供企业微信回调接口
- 一个进程同时跑 Web 服务和定时任务
- 支持全 A 股买点扫描
- 支持同一套规则做历史回测

## 技术栈

- `FastAPI`
- `uvicorn`
- `APScheduler`
- `httpx`
- `akshare`
- `pycryptodome`

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 直接运行

默认端口是 `80`：

```bash
python -m app
```

如果当前机器不是 root，建议临时改成 `8080` 测试：

```bash
APP_PORT=8080 python -m app
```

## 目录

- 应用入口：`app/main.py`
- 命令行入口：`app/__main__.py`
- 定时任务：`app/scheduler.py`
- 股票服务：`app/services/stock_service.py`
- 企业微信发送：`app/services/wecom_service.py`
- 企业微信回调加解密：`app/services/wecom_crypto.py`
- 企业微信回调接口：`app/api/wecom_callback.py`

## 默认行为

- 监控模式默认：`market_buy`
- 信号策略默认：`leader_momentum`
- 股票代码默认：`000725,515120,159530,002653`
- 定时频率默认：`60` 秒
- 回调路径默认：`/wecom/callback`
- 默认监听地址：`0.0.0.0`
- 默认监听端口：`80`
- 推送时段：仅 A 股交易日的 `09:30-11:30`、`13:00-15:00`
- 默认买点规则：超短龙头动量，优先主线板块里的强势龙头

## 可选环境变量

```bash
APP_HOST=0.0.0.0
APP_PORT=80
APP_LOG_LEVEL=INFO
APP_MONITOR_MODE=market_buy
APP_SYMBOLS=000725,515120,159530,002653
APP_POLLING_ENABLED=true
APP_POLLING_INTERVAL_SECONDS=60
APP_POLLING_LOOKBACK_DAYS=20
APP_SIGNAL_ADJUST=qfq
APP_SIGNAL_STRATEGY=leader_momentum
APP_SIGNAL_TOP_N=10
APP_SIGNAL_SCAN_LIMIT=40
APP_SIGNAL_COOLDOWN_MINUTES=120
APP_SIGNAL_HISTORY_DAYS=120
APP_SIGNAL_BREAKOUT_LOOKBACK_DAYS=20
APP_SIGNAL_MIN_PRICE=3
APP_SIGNAL_MIN_CHANGE_PCT=2
APP_SIGNAL_MAX_CHANGE_PCT=9.8
APP_SIGNAL_MIN_TURNOVER_RATE=3
APP_SIGNAL_MIN_VOLUME_RATIO=1.8
APP_SIGNAL_MIN_VOLUME_MULTIPLE=1.5
APP_SIGNAL_MIN_AMOUNT=100000000
APP_SIGNAL_EXCLUDE_ST=true
APP_LEADER_TOP_INDUSTRY_BOARDS=3
APP_LEADER_TOP_CONCEPT_BOARDS=5
APP_LEADER_MAX_SIGNALS_PER_THEME=2
APP_LEADER_MAX_SIGNALS_PER_POOL=3
APP_LEADER_MIN_BOARD_CHANGE_PCT=1.5
APP_LEADER_MIN_CHANGE_PCT=3
APP_LEADER_MAX_CHANGE_PCT=9.8
APP_LEADER_MIN_TURNOVER_RATE=5
APP_LEADER_MIN_VOLUME_RATIO=2
APP_LEADER_MIN_VOLUME_MULTIPLE=1.8
APP_LEADER_MIN_AMOUNT=300000000
APP_LEADER_MIN_PRICE=3
APP_LEADER_MIN_SPEED=0.3
APP_LEADER_MIN_CLOSE_TO_HIGH_RATIO=0.985
APP_LEADER_MIN_CLOSE_IN_RANGE_RATIO=0.65
APP_LEADER_MIN_3DAY_RETURN_PCT=3
APP_BACKTEST_FORWARD_DAYS=1,3,5,10
APP_BACKTEST_SIGNAL_COOLDOWN_DAYS=5

APP_REGIME_ENABLED=true
APP_REGIME_INDEX_SYMBOL=sh000300
APP_REGIME_LOOKBACK_DAYS=20
APP_REGIME_RISK_ON_THRESHOLD=5.0
APP_REGIME_RISK_OFF_THRESHOLD=-3.0
APP_REGIME_RISK_ON_CHANGE_MULT=0.85
APP_REGIME_RISK_ON_AMOUNT_MULT=0.85
APP_REGIME_RISK_OFF_CHANGE_MULT=1.6
APP_REGIME_RISK_OFF_AMOUNT_MULT=1.6
APP_REGIME_RISK_OFF_PAUSE=true

WECOM_CALLBACK_PATH=/wecom/callback
WECOM_CALLBACK_RECEIVE_ID=wwad4729df5fff92cf
WECOM_CALLBACK_TOKEN=stockanalyze2026
WECOM_CALLBACK_ENCODING_AES_KEY=stockanalyze2026abcdefghijklmnopqrstuvwxyz1

WECOM_WEBHOOK_URL=
WECOM_WEBHOOK_KEY=
WECOM_WEBHOOK_BASE_URL=https://qyapi.weixin.qq.com

WECOM_API_BASE_URL=https://qyapi.weixin.qq.com
WECOM_CORP_ID=wwad4729df5fff92cf
WECOM_CORP_SECRET=E8KRmh7MmDj1fakhqkyeKeZxswq4AH6pm3NGkmiL8GA
WECOM_AGENT_ID=1000002
WECOM_TO_USER=
WECOM_TO_PARTY=1
WECOM_TO_TAG=
```

`APP_MONITOR_MODE` 支持两个值：

- `market_buy`：全市场买点扫描并推送
- `symbols`：按 `APP_SYMBOLS` 固定股票列表推送实时快照

`APP_SIGNAL_STRATEGY` 支持两个值：

- `leader_momentum`：超短主线板块 + 龙头动量策略
- `breakout`：通用放量突破策略

## 市场环境 (regime) 切换

策略会根据大盘指数的 lookback 日涨幅自动切换三态:

| 状态 | 触发条件 | 行为 |
|---|---|---|
| RISK_ON (激进) | 大盘 20 日涨幅 ≥ `APP_REGIME_RISK_ON_THRESHOLD` (默认 +5%) | 关键阈值乘以 `APP_REGIME_RISK_ON_*_MULT` (默认 ×0.85,放宽) |
| NEUTRAL (中性) | 其他 | 默认阈值 (与原版一致) |
| RISK_OFF (防御) | 大盘 20 日涨幅 ≤ `APP_REGIME_RISK_OFF_THRESHOLD` (默认 -3%) | 默认直接停止推送 (`APP_REGIME_RISK_OFF_PAUSE=true`);关闭暂停后改为乘以 `APP_REGIME_RISK_OFF_*_MULT` 收紧 |

**关键设计**:
- 默认配置 (`APP_REGIME_ENABLED=true` + 乘数 0.85/1.0/1.6) 在 NEUTRAL 状态下行为与改动前完全一致,零回归。
- `APP_REGIME_ENABLED=false` 可彻底关闭,回退到未引入 regime 时的行为。
- 当前只调整 **涨跌幅门槛** 和 **成交额门槛** 两类阈值;其他阈值 (换手率/量比/MA 等) 保持原值。
- akshare 拉指数失败 → 自动降级到 NEUTRAL,日志告警,不阻断策略。

## 买点规则

### 1. leader_momentum

默认策略，适合超短线盯盘：

- 优先扫描 `强势股池`、`昨日涨停池`、`涨停池`
- 对 `炸板池` 个股做风险过滤，避免明显走弱票再次入选
- 优先扫描强势行业板块、概念板块
- 从强板块中筛选涨幅、成交额、换手、量比都靠前的个股
- 要求股价突破近 `APP_SIGNAL_BREAKOUT_LOOKBACK_DAYS` 日高点
- 要求站上 `MA20`、`MA60`
- 要求收盘/现价接近日内高位
- 要求近 `3` 日已经有动量延续

这一套更接近“主线板块里的龙头股转强/加速”。

### 2. breakout

备选通用突破规则：

- 涨跌幅在 `APP_SIGNAL_MIN_CHANGE_PCT ~ APP_SIGNAL_MAX_CHANGE_PCT`
- 成交额至少 `APP_SIGNAL_MIN_AMOUNT`
- 换手率至少 `APP_SIGNAL_MIN_TURNOVER_RATE`
- 量比至少 `APP_SIGNAL_MIN_VOLUME_RATIO`
- 当日价格突破近 `APP_SIGNAL_BREAKOUT_LOOKBACK_DAYS` 日高点
- 价格站上 `MA20` 和 `MA60`
- 成交量相对近 5 日均量至少放大 `APP_SIGNAL_MIN_VOLUME_MULTIPLE` 倍

## 回测

回测入口：

```bash
python -m app.backtest --start 2026-01-01 --end 2026-06-30
```

只回测指定股票：

```bash
python -m app.backtest --symbols 000725,002653,300657 --start 2026-01-01 --end 2026-06-30
```

说明：

- 不传 `--symbols` 时，会对当前可拉取到的全部 A 股代码做回测
- 输出会包含：
  - 信号数量
  - 各持有周期平均收益
  - 各持有周期胜率
  - 最近命中的信号样本
- 默认评估持有周期：`1,3,5,10` 个交易日
- 回测时如果是 `leader_momentum`，会用同一套超短动量条件做历史筛选
- 当前回测对 `强势池/涨停池/炸板池` 这类盘中特征采用近似替代，适合做第一轮筛选，不等于完整盘口级复盘
- 回测已纳入 regime 过滤,逐日判定大盘环境并应用对应阈值乘数,RISK_OFF 当天不计入信号 (与实盘口径一致)。关闭后 (`APP_REGIME_ENABLED=false`) 回退到原口径

也可以直接复制：

```bash
cp .env.example .env
```

## Linux 部署

Ubuntu 24.04 推荐安装：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

部署后初始化：

```bash
cd /app/stock-analyze
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

启动：

```bash
cd /app/stock-analyze
.venv/bin/python -m app
```

如果你只是临时测试：

```bash
cd /app/stock-analyze
APP_PORT=8080 .venv/bin/python -m app
```

## systemd

```bash
sudo cp deploy/systemd/stock-analyze-polling.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stock-analyze-polling
sudo systemctl status stock-analyze-polling
```

日志：

```bash
tail -f /app/stock-analyze/logs/polling.log
```

## 打包上传

本地打包：

```bash
./scripts/package_release.sh
```

上传：

```bash
scp release/stock-analyze-*.tar.gz user@your-server:/app/
```

服务器解压：

```bash
mkdir -p /app
tar -xzf /app/stock-analyze-*.tar.gz -C /app
```
