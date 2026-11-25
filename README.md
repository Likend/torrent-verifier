# Torrent Verifier

使用 `.torrent` 文件中的 piece hash 校验本地内容是否完整、正确。

校验器会按照 torrent 中记录的文件顺序读取内容，并对每个 piece 计算 SHA-1。支持单文件 torrent、多文件 torrent，以及通过挂载将 torrent 内部路径映射到不同的本地目录。

## 环境要求

- Python 3.12 或更高版本

使用 [uv](https://docs.astral.sh/uv/)，可以直接运行：

```bash
uv run python main.py <torrent-file> <content-path>
```

## 基本用法

```text
python main.py <torrent-file> <content-path>
```

参数说明：

- `<torrent-file>`：输入的 `.torrent` 文件路径。
- `<content-path>`：包含待校验内容的本地根目录。
  - 对于单文件 torrent，传入该文件所在的目录。
  - 对于多文件 torrent，传入包含 torrent 根目录的目录路径。

## 挂载路径

默认情况下，torrent 中的所有路径都相对于 `<content-path>` 查找。使用 `--mount`（或 `-m`）可以把 torrent 内部的某个路径映射到另一个本地目录：

```text
python main.py <torrent-file> <content-path> \
    --mount <torrent-path-1> <mount-to-path-1>
    [--mount <torrent-path-2> <mount-to-path-2> ...]
```

其中：

- `<torrent-path-*>`：torrent 内部路径，使用 `/` 分隔，例如 `Music/Album`。
- `<mount-to-path-*>`：本地挂载目录。

## 查看帮助

```bash
python main.py --help
```
