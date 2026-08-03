# Worker

AI 开发工作区，用于统一沟通方式、项目组织和共享技能。

```text
projects/       独立项目仓库
plans/          本地计划文档（不提交）
.agents/skills/ 共享技能
tmp/            本地临时文件（不提交）
```

新项目先在 `projects/<项目名>/idea/` 整理想法，再在 `plans/<项目名>/` 输出执行计划书与技术方案。

运行 `./scripts/initx.sh` 可初始化或修复工作区结构。详细约定见 [AGENTS.md](AGENTS.md)。
