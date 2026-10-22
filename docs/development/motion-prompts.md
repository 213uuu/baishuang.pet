# 白霜 · 形态转换「中间动作」生成提示词

## 0. 用法（最关键的一条）

**用"首尾帧插值"，不要用纯文生视频。**

- 首帧：现有的 A 姿势帧（例如 `frames/idle/05.png`）
- 末帧：现有的 B 姿势帧（例如 `frames/running/01.png`）
- 提示词只负责描述"**中间怎么动**"

这样角色设计被首末两帧锁死，模型只补运动，一致性比让它自由发挥高一个数量级。
纯文生视频（只给文字）几乎必然会漂：换脸、换衣、长翅膀、镜头乱跑。

## 1. 通用提示词（中文，即梦／国内工具）

```
【角色】Q版约2.5头身的龙娘少女：白色长直发、紫色眼瞳、白色连衣裙、黑色长袜、
深紫色小角、紫红色蝴蝶结发饰、身后一条紫色龙尾（没有翅膀）。冷脸傲娇，
表情细微，不做夸张鬼脸。

【镜头】固定机位，正前方偏左约30度的三四分之三视角，全身入画，人物始终居中，
脚底基线全程固定不动，人物大小比例全程不变。摄像机不推拉、不旋转、不上下移动。

【背景】纯绿色 #00FF00 平坦背景，无阴影、无杂物、无地面。

【动作】从【起始姿势】平滑过渡到【结束姿势】。
运动要求：动作连贯，缓入缓出；视线先行、头部跟随、躯干最后；重心自然转移；
中间不跳变、不闪断、不重复帧；全程四肢数量与结构正确。

【变身光效】只在转换的中段加一层短促的紫白色光晕与粒子，用来遮住姿势切换，
中段1~2帧最强，首帧与末帧的光效必须为0——首末帧要和参考图一模一样。

【风格】日系赛璐璐上色，清晰描边，无运动模糊，无景深虚化。

【禁止】翅膀、恶魔角、额外肢体、多余角色、文字水印、镜头缩放或抖动、
背景变化、服装/发色/瞳色变化、写实风格、3D渲染。
```

## 2. 通用提示词（English，ComfyUI / SDXL / AnimateDiff）

```
chibi anime girl, about 2.5 heads tall, long straight white hair, purple eyes,
white dress, black thighhighs, small dark-purple horns, magenta ribbon hair
ornaments, purple dragon tail (NO wings), tsundere cool expression, subtle face

static camera, three-quarter front view, full body, character centered,
feet on a fixed baseline, constant scale, no zoom, no pan, no rotation, no shake

flat pure green background (#00FF00), no shadow, no props, no ground plane

motion: smooth in-between animation from [START POSE] to [END POSE],
ease in and out, eyes lead then head then torso, natural weight shift,
no frame jumps, consistent limb count and structure

transformation glow: brief purple-white glow and sparkles only in the middle
1-2 frames, zero glow on the first and last frames (they must match the reference)

cel shaded, clean lineart, no motion blur, no depth of field

negative: wings, demon horns, extra limbs, extra fingers, multiple characters,
text, watermark, zoom, camera shake, background change, outfit change,
hair color change, motion blur, realistic, 3d render
```

## 3. 逐动作：把【起始姿势】→【结束姿势】填进去

对照最初定下的交互设计，一共 9 段转换。每段建议 2 秒（24fps 导出，抽帧时每 2 帧取 1）。

| # | 触发 | 起始姿势 | 结束姿势 | 中间动作要点 |
| --- | --- | --- | --- | --- |
| 1 | 启动／打招呼 | 自然站姿 | 自然站姿（轻抬手招呼） | 手臂先微抬再落下；视线先扫过来，头轻颔 |
| 2 | 进入工作 | 自然站姿 | 双手掐腰、低头嫌弃 | 先垂眼，再收臂掐腰；肩略耸，嘴角下撇（不屑） |
| 3 | 工作完成 | 双手掐腰低头 | 昂首、下巴微抬 | 手从腰上放下；胸先挺、下巴后抬，嘴角上扬（得意） |
| 4 | 干活时被点 | 双手掐腰 | 低头害羞心虚 | 先一只脚快速抬起落下跺两下（烦躁），随后肩一缩、头低下去、脸颊泛红、眼神向左下躲 |
| 5 | 空闲时被点 | 自然站姿 | 抬头／歪头看镜头 | 眼球先动，再头随；身体不动，只用脖子 |
| 6 | 害羞 | 抬头看镜头 | 低头缩肩害羞 | 眼神先躲开，随后低头、双手攥到身前、脸颊泛红 |
| 7 | 连点炸毛 | 自然站姿 | 抱胸瞪眼、张嘴 | 身体轻微前后晃，眉压低、嘴张开；发丝随动作轻甩 |
| 8 | 偷看被发现 | 低头 | 低头害羞 | 头先快速转向镜头（只1~2帧），立刻转回并低下去，脸红、眼神躲闪 |
| 9 | 收工告别 | 昂首 | 低头害羞 | 视线垂下、肩放松、头低下去；半步侧身但不转身背对 |

## 4. 参数建议

- 时长 **2 秒**，比例 **1:1**，运动强度选**中低**（高了会糊还会变形）
- 导出 **24fps**，抽帧时**每 2 帧取 1 帧**（等于 12fps），再交给我
- 光效用**低强度、短时长**：整段发光会让人物细节丢失，抠出来的帧会发虚

## 5. 为什么这么写（踩过的坑）

- 「龙娘」这个词会让模型自动加**翅膀和恶魔角**——必须在提示词和负面词里都点名排除
- 不写「固定机位／固定基线」，模型会自己推镜头、人物会缩放漂移，后期对齐救不回来
- 不写「首末帧光效为0」，模型会把整段都发光，首尾帧就跟参考图对不上
- 不写「纯绿背景」，模型会给渐变、阴影、地面，抠像会留边
- 逐帧生成的方案已经证明做不到角色一致（换脸换衣），所以要么首尾帧插值，要么就别用 AI 补帧

## 6. 我拿到之后怎么接

1. 抠掉绿色背景 → 得到带 alpha 的帧
2. 与现成立绘做**整帧互相关对齐**（对齐判据：残差降幅 ≥45% 且位移 ≤3 像素才平移）
3. 按 192×208 归一化（以脚底基线与同一缩放为基准，避免忽大忽小）
4. 放进 `frames/trans-<旧状态>-<新状态>/`，程序切换状态时会自动先播这一段
