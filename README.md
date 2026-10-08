# 📊 Daily Global Finance Digest (全球财经与综合热点早报)

借助 **GitHub Actions** 云端免维护定时调度，每天定时自动抓取全球财经宏观、市场动向与综合头条，提炼为精炼晨报，并通过 **Bark** 自动推送到你的 iPhone 锁屏弹窗。

> **无需开机、无需本地服务器、零成本**，电脑关机也不影响每日准时接收。

---

## 🚀 极速上手（3 步完成）

### 第一步：在 iPhone 上安装 Bark
1. 打开 App Store 搜索并下载 **[Bark](https://apps.apple.com/app/bark-customed-notifications/id1403753874)**（免费开源）。
2. 打开 Bark App，在主页会看到你的专属推送链接，例如：
   `https://api.day.app/AbCdEfGhIjK12345/`
3. 复制中间那串长字符串 `AbCdEfGhIjK12345`，这就是你的 **`BARK_KEY`**。

---

### 第二步：将代码推送到你的 GitHub 仓库
在本地执行以下命令（如果你已有仓库，直接 push 即可）：

```bash
cd /Users/ding/.gemini/antigravity/scratch/global-finance-digest
git init
git add .
git commit -m "feat: init global finance digest workflow"
# 在 GitHub 上新建一个名为 global-finance-digest 的私有 (Private) 仓库，然后关联推送：
git remote add origin https://github.com/你的用户名/global-finance-digest.git
git branch -M main
git push -u origin main
```

---

### 第三步：在 GitHub 仓库添加 Secrets（密钥）
1. 打开你在 GitHub 上的该仓库，点击 **Settings** -> **Secrets and variables** -> **Actions**。
2. 点击 **New repository secret**，添加必要密钥：
   * **Name**: `BARK_KEY`
   * **Secret**: 粘贴你在第一步中获取的 Bark Key
3. *(可选增强)*：如果你希望使用大模型进行更聪明的专业分析，可额外添加：
   * `GEMINI_API_KEY`（免费 Google Gemini API Key）或 `OPENAI_API_KEY`（DeepSeek / OpenAI 等）。
   * 若不配置，脚本会自动使用内置的高质量版式进行精炼排版。

---

### ⏱️ 定时与手动测试
* **自动运行**：默认在 **每天北京时间早上 08:00 (UTC 00:00)** 自动触发并推送。
* **手动测试**：随时进入 GitHub 仓库页面，点击 **Actions** -> **Daily Global Finance Digest** -> **Run workflow**，即可立即测试并查看手机推送效果！
