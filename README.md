# SJTU_ThesisCrawler_2026
# 上海交通大学学位论文下载
上海交大学位论文系统爬取下载工具

## 背景与问题：
[http://thesis.lib.sjtu.edu.cn/](http://thesis.lib.sjtu.edu.cn/)，该网站是上海交通大学的学位论文下载系统，收录了交大的硕士博士的论文。
该系统不便之处在于：
  1.加载缓慢，来回翻阅不便
  2.无法离线查阅，不能想在哪看在哪看
  3.使用手机平板查阅时极其不方便
有学长曾经做过(https://github.com/olixu/SJTU_Thesis_Crawler)，该方案目前2026年已失效，因此这里提供新的解决方案。

## 配置要求：
参考requirements.txt

## 使用：
可以提前在网站检索需要的论文，复制标题后
```bash
python ThesisD.py
```
输入标题，然后静候完成
(注：有部分论文的某些页面会有服务器问题带来的损坏因此无法获取)
 
## Outlooking
目前仅支持单论文按题目检索下载，后续可以丰富检索并且引入批量化操作
