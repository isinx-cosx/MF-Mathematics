// mf_export.h — DLL 导出/导入宏。
//
// 构建 DLL 时(mf_mathematics 目标定义 MF_BUILD_DLL)符号导出;
// 调用方链接导入库时符号按 dllimport 声明。

#pragma once

#ifdef MF_BUILD_DLL
#define MF_API __declspec(dllexport)
#else
#define MF_API __declspec(dllimport)
#endif
