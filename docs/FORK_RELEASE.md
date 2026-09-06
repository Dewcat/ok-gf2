# Dewcat fork 发布

本 fork 使用 `.github/workflows/build.yml` 在 GitHub Actions 上自动生成 Windows 安装包。
安装和更新源为 `https://github.com/Dewcat/ok-gf2.git`。

## 发布新版本

1. 将准备发布的代码推送到本 fork。
2. 在该提交上创建一个尚未使用的版本标签，例如 `v1.2.74`。
3. 将这个标签推送到 **Dewcat/ok-gf2**，触发自动发布。

在当前本地工作副本中，`fork` 远端指向 Dewcat 仓库：

```powershell
git remote get-url fork
git tag -a v1.2.74 -m "Dewcat fork release v1.2.74"
git push fork refs/tags/v1.2.74
```

推送前确认标签指向待发布的提交。版本号使用启动器支持的 `v数字.数字.数字` 格式，
每次递增，并在工作流的 Release 说明中更新本次改动。

## 自动流程

- Windows runner 安装 Python 3.12 和项目依赖。
- 在独立 Python 进程中执行 `tests/Test*.py`，也包括 `test_clear_map_planner.py`。
- 根据 PyAppify 版本、构建配方、目标架构、`pyappify.yml` 和图标的哈希查找兼容启动器。
- 复用本 fork Release 中 SHA-256 验证通过的启动器；没有匹配项时才编译。
- 使用 Zlib 压缩生成完整安装包和在线安装包，并核对包内版本与发布标签一致。
- 为附件添加版本号，生成 `SHA256SUMS.txt`，保存 Actions 构建产物。
- 构建成功后自动创建 GitHub Release，当前默认标记为测试版。

完整安装包名为 `ok-gf2-win32-dewcat-setup-版本号.exe`；
在线安装包名为 `ok-gf2-win32-online-setup-版本号.exe`。
GitHub 自动提供的 Source code 压缩包是源码，不是安装包。

## 查看和重试

在 [Actions 页面](https://github.com/Dewcat/ok-gf2/actions/workflows/build.yml) 查看日志。
失败时优先使用 **Re-run failed jobs**；不要移动已经发布的版本标签。

也可以对已有标签手动触发同一流程：

```powershell
gh workflow run build.yml --repo Dewcat/ok-gf2 --ref v1.2.73
```

手动选择普通分支只构建 Actions 附件，选择版本标签才会创建 Release。
此流程只需要仓库自带的 `GITHUB_TOKEN`，不需要上游的 CNB、GH_TOKEN 或 MirrorChyan 密钥。

## 启动器复用

`scripts/release_launcher.py` 将兼容性和附件校验信息写入 `launcher-manifest.json`。
修改 Python 任务不会触发启动器重编译；修改图标或启动器配置则会。
首个没有清单的 `v1.2.73` 仅在它仍指向已知的 `6f2141d` 提交、构建输入一致时允许复用。
如果改变启动器的编译方法，需要同步更新脚本中的 `BINARY_RECIPE`，以使旧启动器失效。

定制的 PyAppify Action 位于 `.github/actions/pyappify`，保留上游来源与许可证。
`compression: zlib` 只控制安装包压缩，不要求重编译启动器；相比 LZMA，完整包可能更大。
