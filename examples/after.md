# 实验三 开源许可证扫描

## 一、实验目标

用 ScanCode Toolkit 扫描 Apache Commons-IO 仓库，统计各文件的许可证和版权声明，并和 `pom.xml` 里声明的许可证对照。

## 二、实验过程

### 2.1 安装

安装 ScanCode 时反复失败，原因是网络在传输大文件时不稳定，换成有线网络后才装上。排查过程如下。

执行 `pip install scancode-toolkit` 时连续 5 次失败，报错为 `SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING]'))`。

我最初认为是下载源的问题，于是改用清华 TUNA 镜像。改用后 SSL 握手正常，但主文件下载到约 34 MB 时出现 `ReadTimeoutError`。把超时改为 60 秒、重试改为 10 次后，仍然在同一位置失败，所以问题出在网络传输大文件时不稳定。换成有线网络后安装成功。

### 2.2 扫描

扫描命令如下：

```bash
scancode -clpieu --json-pp result.json commons-io/
```

处理流程如图 2-1 所示，先读取文件，再识别许可证，然后提取版权声明，最后输出 JSON。

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {
  'primaryColor': '#ffffff', 'primaryBorderColor': '#000000',
  'primaryTextColor': '#000000', 'lineColor': '#000000'},
  'flowchart': {'curve': 'linear'}}}%%
flowchart LR
  A[读取文件] --> B[识别许可证]
  B --> C[提取版权声明]
  C --> D[输出 JSON]
```

图 2-1 ScanCode 扫描流程

整个过程用时 123.97 秒，其中识别许可证这一步占 120.03 秒。

## 三、实验结果

本次扫描的覆盖率较高，源码文件全部检出了许可证，没有检出的都是非源码文件。共扫描 698 个文件，检出情况见表 3-1。

表 3-1 许可证检出情况

| 类别 | 文件数 |
|---|---|
| 检出许可证 | 628 |
| 未检出 | 70 |

检出许可证的文件里，571 个 Java 源文件全部是 apache-2.0，与 `pom.xml` 中的声明一致。未检出的 70 个文件中，`.bin` 35 个、`.txt` 21 个、`.zip` 6 个，其余是图片，没有源码文件。

## 四、局限

这个结论有两个限制。第一，ScanCode 只扫描仓库里实际存在的文件，不解析 Maven 依赖树，所以只能说明仓库自身没有声明冲突。第二，工具给出的是检测结果，许可证之间的兼容性还需要人工判断。
