# 设计稿索引｜商品管理后台

本目录是「简易商品管理网站」的视觉设计交付物：一份规范文档 + 5 张 1440 × 900 高保真设计稿（HTML 源文件 + 2 倍 PNG 导出图）。规范正文见 [product-admin-design.md](product-admin-design.md)。

## 1. 目录结构

```
docs/design/
├── README.md                    # 本文件：索引、截图方法、与前端页面的对应关系
├── product-admin-design.md      # 设计规范：原则 / Token / 布局 / 组件 / 交互状态
├── mockups/                     # 自包含 HTML（无外网依赖，双击即可查看）
│   ├── 01-product-list.html
│   ├── 02-product-form.html
│   ├── 03-category-manage.html
│   ├── 04-empty-state.html
│   └── 05-dashboard.html
└── images/                      # 2880 × 1800（1440 × 900 @2x）PNG 导出图
    ├── 01-product-list.png
    ├── 02-product-form.png
    ├── 03-category-manage.png
    ├── 04-empty-state.png
    └── 05-dashboard.png
```

## 2. 设计稿索引

| 编号 | 页面 / 状态 | PNG（2880 × 1800） | HTML 源文件 | 内容要点 |
| --- | --- | --- | --- | --- |
| 01 | 商品列表 | [01-product-list.png](images/01-product-list.png) | [01-product-list.html](mockups/01-product-list.html) | 三张统计卡（商品总数 8 / 分类数 4 / 筛选结果 8）+ 搜索区 + 8 行商品表格（ID 倒序，含上架/下架 Tag、¥ 两位小数右对齐、库存 0）+ 分页「共 8 条」；第 5 行标注 hover 态 |
| 02 | 新增商品弹窗（含错误态） | [02-product-form.png](images/02-product-form.png) | [02-product-form.html](mockups/02-product-form.html) | 480px 表单弹窗盖在列表页上；5 个字段，价格填入 `12.345` 触发红框 + 红字「价格最多 2 位小数，且不能小于 0」；含 8/50 字数、上架开关 |
| 03 | 分类管理（含删除确认） | [03-category-manage.png](images/03-category-manage.png) | [03-category-manage.html](mockups/03-category-manage.html) | 4 个分类（饮料 3 / 零食 3 / 乳品 2 / 冲调饮品 0）、商品数占比条、420px 删除确认弹窗（「冲调饮品」可安全删除），底部「分类操作说明」卡 |
| 04 | 空态（搜索无结果） | [04-empty-state.png](images/04-empty-state.png) | [04-empty-state.html](mockups/04-empty-state.html) | 关键词「巧克力」筛选后 0 条：表头保留、插图 + 「没有符合条件的商品」+ 说明 + 「清空筛选」，分页「共 0 条」 |
| 05 | 概览 | [05-dashboard.png](images/05-dashboard.png) | [05-dashboard.html](mockups/05-dashboard.html) | 四联统计（8 / 4 / 上架 6 · 75% / 下架 2 · 25%）、各分类商品数分布条、上架状态环形图、库存预警 2 条（坚果 0 / 酸奶 18）、最近新增 4 条 |

示例数据全部为真实中文商品（可口可乐、百事可乐、雪碧、乐事薯片、奥利奥饼干、三只松鼠每日坚果、伊利纯牛奶、蒙牛酸奶），与后端 `python/fastapi-demo` 的 3 个 seed 分类（饮料 / 零食 / 乳品）一致；「冲调饮品」为演示「空分类可删除」新增的第 4 个分类。

## 3. 与前端页面的对应关系

| 设计稿 | 路由 | 实现文件 | 说明 |
| --- | --- | --- | --- |
| 01 | `/products` | `fullstack/product-admin/src/views/ProductList.vue` | 列表页默认态；统计卡 + 搜索区 + 表格 + 分页 |
| 02 | `/products`（弹窗） | `src/components/ProductFormDialog.vue` | 新增与编辑共用同一弹窗，标题切换「新增商品 / 编辑商品」，错误态样式一致 |
| 03 | `/categories` | `src/views/CategoryManage.vue` + `src/components/CategoryFormDialog.vue` | 分类表格、商品数占比条、删除确认（用 `ElMessageBox` 或自定弹窗保持 420px / 红底删除按钮） |
| 04 | `/products`（空态） | `src/views/ProductList.vue` 空态分支 | `ElTable` 的 `empty` 插槽：表头保留、插图 + 主副文案 + 「清空筛选」 |
| 05 | `/`（概览） | `src/views/Dashboard.vue` | 四联统计 + 分类分布 + 环形图 + 库存预警 + 最近新增 |

公共部分：布局壳（200px 侧栏 + 56px 顶栏）在 `src/App.vue`；统计卡在 `src/components/StatCard.vue`；全部颜色 / 字号 / 间距 / 圆角 / 阴影以 [product-admin-design.md 第 2 节](product-admin-design.md) 的 token 为准，前端落在 `src/styles/index.css` 的 `--pa-*` 变量上，并同步覆盖 Element Plus 的 `--el-color-*`。

## 4. 查看与重新导出

- **查看设计稿**：用浏览器（建议 1440 px 以上视口）直接打开 `mockups/*.html`；文件内联了全部 CSS 与 SVG 图标，不依赖网络，也不需要构建。
- **直接看图片**：`images/*.png` 为 2 倍图（2880 × 1800），并排对比或贴进文档时按 1440 × 900 显示。

重新导出 PNG（macOS + 系统 Chrome，无头截图 → 裁剪到 1440 × 900 @2x）：

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --hide-scrollbars --no-sandbox --disable-gpu \
  --user-data-dir=/tmp/pa-shot-profile \
  --screenshot=/tmp/01.png --window-size=1440,1000 --force-device-scale-factor=2 \
  "file://$PWD/mockups/01-product-list.html"
# 再裁掉底部多出的 100px：得到 2880 × 1800
python3 -c "
from PIL import Image
Image.open('/tmp/01.png').crop((0,0,2880,1800)).save('images/01-product-list.png')"
```

说明：

- 视口高度取 1000px 再裁剪到 1800 设备像素，是为了避开 Chrome 无头模式在视口最底部偶发的重绘残影；页面本身是 1440 × 900 的固定画布，顶部对齐，裁剪后与 900px 视口渲染完全一致。
- 必须带 `--force-device-scale-factor=2`（2 倍图）；必须带 `--no-sandbox` 与独立 `--user-data-dir`，否则在部分 macOS 环境下会静默不产出文件。
- 导出后逐张检查：文字无溢出/截断、卡片无重叠、表格末行与分页条之间无异常空白、底部无残影。

## 5. 自检清单（v1.0 已通过）

- [x] 5 张设计稿齐备，均为 2880 × 1800 PNG（@2x）与对应自包含 HTML
- [x] 颜色、字号、间距、圆角、阴影与 design.md 第 2 节 token 一一对应，无临时数值
- [x] 商品数据为真实中文商品，价格 `¥` 两位小数右对齐，状态为上架（绿）/ 下架（灰）Tag
- [x] 覆盖列表分页、搜索筛选、新增弹窗错误态、分类删除确认、空态、概览统计、加载态规范
- [x] 无 lorem / TODO / 占位符文案，无外网 CDN 依赖
- [x] 表格行高 48px、表头 44px、侧栏 200px、顶栏 56px、内容内边距 24px 与规范一致
