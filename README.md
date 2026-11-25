# Torrent verifier

根据 `bencodepy.decode` 输出校验 torrent 文件。校验器依赖 `FileSystem` 接口，文件系统的 `open()` 返回标准库二进制文件对象，因此可在测试中注入返回 `io.BytesIO` 的实现，不需要生产代码里的 mock 文件系统。

## 设计

- `load_torrent`：调用 `bencodepy.decode`，然后交给 `TorrentMetadata.from_bencode`。
- `TorrentMetadata.from_bencode`：将 bencode 解码结果转换为领域模型，并保留 torrent 文件顺序。
- `TorrentMetadata`：计算每个文件在 torrent 拼接数据中的 `[start, end)` 位置。
- `TorrentVerifier`：严格按 torrent 文件顺序拼接读取数据，按 piece 校验 SHA-1；piece 跨文件时会分别读取文件的对应区间。

## 使用

直接传入 `.torrent` 文件：

```text
python verify_torrent.py file.torrent D:\\Downloads\\content
```

输出中的位置是 torrent 拼接数据的字节区间，采用半开区间 `[start, end)`。

## 测试

```text
python -m pytest
```
