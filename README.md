# stock-analyze

当前项目已接入 `akshare`，采用的是“Java 调用 Python 适配层”的方式：

1. Java 侧通过 `AkshareClient` 发起请求。
2. Python 侧 `scripts/akshare_bridge.py` 负责调用 `akshare`。
3. Python 返回统一的 JSON 结果，Java 再解析成 `JsonNode`。

这样保留了 Maven 项目的结构，也避免了把 Python 金融数据生态强行搬到 JVM 内。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 运行示例

```bash
WECOM_CORP_ID=your-corp-id \
WECOM_CORP_SECRET=your-corp-secret \
WECOM_AGENT_ID=1000002 \
WECOM_TO_PARTY=1 \
APP_SYMBOL=600519 mvn -DskipTests package
java -jar target/stock-analyze-1.0.0-SNAPSHOT.jar
```

当前项目现在是一个标准 Spring Boot Web 服务：

- 内嵌 HTTP 服务，默认端口 `80`
- 企业微信回调 URL：默认 `/wecom/callback`
- 定时任务每 `1` 分钟执行一次，抓股票并发企业微信
- 一个进程同时提供 Web 接口和定时任务，不需要再拆成两个服务

当前主程序会在拿到数据后直接把同样的信息作为文本消息发到企业微信；如果企业微信参数没有配齐，程序会在启动时直接报错。

如果你要接别的 AkShare 接口，直接复用 `AkshareClient.invoke(functionName, params)` 即可。

## 企业微信回调 URL

如果你要在企业微信后台配置“接收消息服务器URL”，当前 Spring Boot 服务启动后就会直接提供这个接口。

默认监听：

- 端口：`80`
- 路径：`/wecom/callback`

也支持环境变量覆盖：

- `SERVER_PORT`
- `WECOM_CALLBACK_RECEIVE_ID`
- `WECOM_CALLBACK_TOKEN`
- `WECOM_CALLBACK_ENCODING_AES_KEY`

当前代码内置的默认回调配置：

- `receiveId`: `wwad4729df5fff92cf`
- `token`: `stock-analyze-token`
- `EncodingAESKey`: `yDJGijqy+YHErEFLuf5g2e/zIcxu7azZN16kJT3rkds`

企业微信后台配置“接收消息服务器URL”时：

1. URL 填你自己的公网地址，例如 `https://your-domain.com/wecom/callback`
2. Token 填 `stock-analyze-token`
3. EncodingAESKey 填 `yDJGijqy+YHErEFLuf5g2e/zIcxu7azZN16kJT3rkds`

说明：

- “可信域名”本身主要是后台配置项，不需要项目额外写业务代码
- “接收消息服务器URL”才需要本地服务端逻辑，当前已经实现 URL 验证和消息解密
- 如果你本地直接启动，企业微信后台无法访问 `localhost`，需要把服务部署到公网，或者用内网穿透映射出一个公网 HTTPS 地址

默认会优先查找：

1. 环境变量 `AKSHARE_PYTHON`
2. 项目目录下的 `.venv/bin/python` 或 `.venv/Scripts/python.exe`
3. 最后才回退到系统 `python3`

如果你想显式指定 Python，也可以这样跑：

```bash
AKSHARE_PYTHON=.venv/bin/python java -jar target/stock-analyze-1.0.0-SNAPSHOT.jar
```

## 可复用入口

- Java 客户端：`src/main/java/com/zyl/stockanalyze/akshare/AkshareClient.java`
- 股票服务封装：`src/main/java/com/zyl/stockanalyze/akshare/AkshareStockService.java`
- Python 桥接脚本：`scripts/akshare_bridge.py`
- 定时任务：`src/main/java/com/zyl/stockanalyze/StockPollingJob.java`

## 可选环境变量

- `AKSHARE_PYTHON`: 指定 Python 解释器路径
- `AKSHARE_BRIDGE_SCRIPT`: 指定桥接脚本路径
- `WECOM_WEBHOOK_URL`: 企业微信群机器人完整 Webhook 地址
- `WECOM_WEBHOOK_KEY`: 企业微信群机器人 key; 配置后会自动拼成 Webhook 地址
- `WECOM_CORP_ID`: 企业微信 CorpID
- `WECOM_CORP_SECRET`: 企业微信应用 Secret
- `WECOM_AGENT_ID`: 企业微信应用 AgentId
- `WECOM_TO_USER`: 企业微信消息接收成员
- `WECOM_TO_PARTY`: 企业微信消息接收部门，支持部门 ID
- `WECOM_TO_TAG`: 企业微信消息接收标签
- `WECOM_API_BASE_URL`: 可选，自定义企业微信 API 地址，主要用于测试
- `WECOM_WEBHOOK_BASE_URL`: 可选，自定义群机器人 API 地址，主要用于测试

通知启用优先级：

1. `WECOM_WEBHOOK_URL` / `WECOM_WEBHOOK_KEY`
2. `WECOM_CORP_ID` + `WECOM_CORP_SECRET` + `WECOM_AGENT_ID` + (`WECOM_TO_USER` / `WECOM_TO_PARTY` / `WECOM_TO_TAG`)

示例：

```bash
WECOM_WEBHOOK_KEY=your-key java -jar target/stock-analyze-1.0.0-SNAPSHOT.jar
```

## Linux 部署

当前项目运行时依赖：

- Java 17+
- Python 3.9+
- `python3-venv`

如果你在 Linux 服务器上现场编译，才需要 Maven 3.6+。

在 Ubuntu Server 24.04 LTS 上，推荐直接安装 `openjdk-17-jdk`。

推荐最小安装：

```bash
sudo apt update
sudo apt install -y git openjdk-17-jdk python3 python3-venv python3-pip
```

如果 `python3-venv` 提示找不到，可以先启用 `universe` 再安装：

```bash
sudo add-apt-repository universe
sudo apt update
sudo apt install -y git openjdk-17-jdk python3 python3-venv python3-pip
```

注意：`akshare==1.18.64` 要求 `Python >= 3.9`。如果你的服务器自带的是 `Python 3.6/3.7/3.8`，会出现：

```bash
ERROR: Could not find a version that satisfies the requirement akshare==1.18.64
```

这时需要改用 `Python 3.9+`，并在部署时显式指定：

```bash
APP_HOME=/opt/stock-analyze PYTHON_BIN=/usr/bin/python3.9 ./scripts/deploy_linux.sh
```

部署文件已经生成：

- 环境变量模板：`.env.example`
- 一键部署脚本：`scripts/deploy_linux.sh`
- 主启动脚本：`scripts/start_polling.sh`
- systemd 服务：`deploy/systemd/stock-analyze-polling.service`

### 1. 部署代码

```bash
cd /opt
git clone <your-repo-url> stock-analyze
cd /opt/stock-analyze
cp .env.example .env
```

修改 `.env` 里的密钥和参数。

如果你没有 git 仓库，可以直接本地打包后上传：

本地执行：

```bash
chmod +x scripts/package_release.sh
./scripts/package_release.sh
```

这个脚本会先在本地执行 `mvn -DskipTests package`，然后把 Spring Boot 可执行 jar 一并打进压缩包里，所以 Linux 服务器上可以不装 Maven。

会生成一个压缩包到 `release/` 目录，例如：

```bash
release/stock-analyze-20260629143000.tar.gz
```

上传到 Linux 服务器：

```bash
scp release/stock-analyze-*.tar.gz user@your-server:/opt/
```

然后在服务器上解压：

```bash
cd /opt
mkdir -p stock-analyze
tar -xzf stock-analyze-*.tar.gz -C stock-analyze
cd stock-analyze
cp .env.example .env
```

### 2. 执行部署脚本

```bash
chmod +x scripts/deploy_linux.sh scripts/start_polling.sh
APP_HOME=/opt/stock-analyze PYTHON_BIN=python3 ./scripts/deploy_linux.sh
```

如果你上传的是 `scripts/package_release.sh` 生成的压缩包，部署脚本会自动检测 `target/stock-analyze-1.0.0-SNAPSHOT.jar`，然后跳过 Maven 编译。

如果你就是想强制跳过 Maven，也可以这样：

```bash
APP_HOME=/opt/stock-analyze PYTHON_BIN=python3 SKIP_MAVEN_BUILD=true ./scripts/deploy_linux.sh
```

### 3. 手工启动验证

启动 Spring Boot 主服务：

```bash
./scripts/start_polling.sh
```

启动后会同时具备两类能力：

- 每 1 分钟拉取一次股票数据并发送到企业微信
- 对外提供企业微信回调接口 `http://your-host/wecom/callback`

### 4. 配置 systemd

复制服务文件：

```bash
sudo cp deploy/systemd/stock-analyze-polling.service /etc/systemd/system/
sudo systemctl daemon-reload
```

开机自启并启动：

```bash
sudo systemctl enable --now stock-analyze-polling
```

查看状态：

```bash
sudo systemctl status stock-analyze-polling
```

查看日志：

```bash
tail -f /opt/stock-analyze/logs/polling.log
```

### 5. 端口说明

默认主服务会同时启动企业微信回调 HTTP 服务，所以你需要放通你配置的回调端口，默认是：

- `80`

如果企业微信后台要求你填写公网可访问 URL，你需要把服务器公网 IP 或域名直接指到这台机器，并确保安全组、防火墙和运营商侧没有拦截这个端口。
