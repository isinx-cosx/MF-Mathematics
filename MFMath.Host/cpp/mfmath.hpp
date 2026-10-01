#pragma once
// mfmath.hpp — 控制台里 C++ 代码调用引擎的唯一门面。
//
// 设计约束（与项目一致）：**计算全部由 C++ 引擎（mf_mathematics.dll）完成**，
// 这个头文件只做参数封装与 JSON 编解码，自己不做任何数学。
//
// 用法：
//
//     #include "mfmath.hpp"
//     #include <iostream>
//
//     int main() {
//         std::cout << mfm::num("expr_eval", {{"expr", "x^2"}, {"x", 3}}) << "\n";   // 9
//         std::cout << mfm::text("diff", {{"expr", "xe^x"}, {"var", "x"}}) << "\n";  // x*exp(x) + exp(x)
//         std::cout << mfm::text("limit", {{"expr", "(1+1/x)^x"}, {"var", "x"}, {"point", "oo"}}) << "\n";
//         if (mfm::exists("solve")) { /* ... */ }
//     }
//
// 编译器需要能找到 mf_mathematics.dll 的导入库（宿主自动生成并传入 -L/-l），
// 运行时需要能找到 mf_mathematics.dll 及其依赖（宿主把引擎目录加进 PATH）。
//
// 引擎约定：math_call 返回形如 {"isError":false,"value":...} 的 JSON；
// isError 为 true 时 value 是中文错误说明 → mfm::Error 抛出。

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#ifndef _WIN32
#error "mfmath.hpp 依赖 Windows 上的 mf_mathematics.dll"
#endif

extern "C" {
__declspec(dllimport) bool function_exists(const char* function_name);
__declspec(dllimport) int math_call(const char* name, const char* args_json,
                                    char* out_buffer, int out_size);
}

namespace mfm {

// ══════════════════════════ 错误 ══════════════════════════

/// 引擎返回 {isError:true} 时抛出，what() 是引擎给的中文说明。
class Error : public std::runtime_error {
public:
    explicit Error(const std::string& msg) : std::runtime_error(msg) {}
};

// ══════════════════════════ 极简 JSON ══════════════════════════
//
// 只实现引擎通信需要的那部分：null / bool / number / string / array / object。
// object 用 vector<pair> 保序（引擎返回的字段顺序对展示有意义）。

class Json {
public:
    enum class Kind { Null, Bool, Number, String, Array, Object };

    Json() : kind_(Kind::Null) {}
    Json(std::nullptr_t) : kind_(Kind::Null) {}
    Json(bool b) : kind_(Kind::Bool), bool_(b) {}
    Json(int v) : kind_(Kind::Number), num_(static_cast<double>(v)) {}
    Json(long long v) : kind_(Kind::Number), num_(static_cast<double>(v)) {}
    Json(double v) : kind_(Kind::Number), num_(v) {}
    Json(const char* s) : kind_(Kind::String), str_(s ? s : "") {}
    Json(const std::string& s) : kind_(Kind::String), str_(s) {}
    Json(std::string&& s) : kind_(Kind::String), str_(std::move(s)) {}
    Json(const std::vector<Json>& a) : kind_(Kind::Array), arr_(a) {}

    static Json array() { Json j; j.kind_ = Kind::Array; return j; }
    static Json object() { Json j; j.kind_ = Kind::Object; return j; }

    /// mfm::Json::object({{"expr","x^2"},{"x",3}})
    static Json object(std::initializer_list<std::pair<std::string, Json>> fields) {
        Json j = object();
        for (const auto& f : fields) j.obj_.push_back(f);
        return j;
    }
    static Json array(std::initializer_list<Json> items) {
        Json j = array();
        for (const auto& i : items) j.arr_.push_back(i);
        return j;
    }

    Kind kind() const { return kind_; }
    bool is_null() const { return kind_ == Kind::Null; }
    bool is_bool() const { return kind_ == Kind::Bool; }
    bool is_number() const { return kind_ == Kind::Number; }
    bool is_string() const { return kind_ == Kind::String; }
    bool is_array() const { return kind_ == Kind::Array; }
    bool is_object() const { return kind_ == Kind::Object; }

    bool as_bool() const {
        require(Kind::Bool, "bool");
        return bool_;
    }
    double as_number() const {
        require(Kind::Number, "number");
        return num_;
    }
    const std::string& as_string() const {
        require(Kind::String, "string");
        return str_;
    }
    const std::vector<Json>& as_array() const {
        require(Kind::Array, "array");
        return arr_;
    }
    const std::vector<std::pair<std::string, Json>>& as_object() const {
        require(Kind::Object, "object");
        return obj_;
    }
    const std::vector<std::pair<std::string, Json>>& fields() const { return as_object(); }

    /// 对象取值：找不到返回 nullptr（不抛异常）。
    const Json* find(const std::string& key) const {
        if (kind_ != Kind::Object) return nullptr;
        for (const auto& kv : obj_)
            if (kv.first == key) return &kv.second;
        return nullptr;
    }
    bool has(const std::string& key) const { return find(key) != nullptr; }

    /// 对象取值：找不到或类型不符抛 Error（错误信息带字段名，便于定位）。
    const Json& at(const std::string& key) const {
        const Json* v = find(key);
        if (!v) throw Error("引擎返回里没有字段 \"" + key + "\"：" + dump());
        return *v;
    }
    const Json& operator[](const std::string& key) const { return at(key); }
    const Json& operator[](std::size_t i) const {
        require(Kind::Array, "array");
        if (i >= arr_.size()) throw Error("数组下标越界：" + std::to_string(i));
        return arr_[i];
    }
    std::size_t size() const {
        if (kind_ == Kind::Array) return arr_.size();
        if (kind_ == Kind::Object) return obj_.size();
        if (kind_ == Kind::String) return str_.size();
        return 0;
    }

    /// 人类可读的 JSON 文本（引擎结果与报错信息都用它展示）。
    std::string dump() const {
        std::string out;
        write(out);
        return out;
    }

    // ── 解析 ──
    static Json parse(const std::string& text) {
        Parser p(text);
        p.skip_ws();
        Json v = p.value();
        p.skip_ws();
        if (!p.eof()) throw Error("JSON 尾部有多余内容");
        return v;
    }

    // ── 数字格式：整数原样，其它 17 位有效数字（不丢精度）──
    static std::string number_to_string(double v) {
        if (std::isnan(v)) return "null";
        if (std::isinf(v)) return v > 0 ? "\"oo\"" : "\"-oo\"";
        if (v == static_cast<double>(static_cast<long long>(v)) &&
            std::fabs(v) < 9.0e15) {
            return std::to_string(static_cast<long long>(v));
        }
        char buf[40];
        std::snprintf(buf, sizeof(buf), "%.17g", v);
        // %.17g 会把 0.1 打印成 0.10000000000000001，缩到能往返的最短形式
        for (int prec = 1; prec <= 17; ++prec) {
            char t[40];
            std::snprintf(t, sizeof(t), "%.*g", prec, v);
            if (std::strtod(t, nullptr) == v) {
                std::snprintf(buf, sizeof(buf), "%s", t);
                break;
            }
        }
        return std::string(buf);
    }

private:
    Kind kind_;
    bool bool_ = false;
    double num_ = 0;
    std::string str_;
    std::vector<Json> arr_;
    std::vector<std::pair<std::string, Json>> obj_;

    void require(Kind want, const char* name) const {
        if (kind_ != want)
            throw Error(std::string("值的类型不是 ") + name + "：" + dump());
    }

    static void escape_into(const std::string& s, std::string& out) {
        out.push_back('"');
        for (unsigned char c : s) {
            switch (c) {
                case '"': out += "\\\""; break;
                case '\\': out += "\\\\"; break;
                case '\n': out += "\\n"; break;
                case '\r': out += "\\r"; break;
                case '\t': out += "\\t"; break;
                case '\b': out += "\\b"; break;
                case '\f': out += "\\f"; break;
                default:
                    if (c < 0x20) {
                        char b[8];
                        std::snprintf(b, sizeof(b), "\\u%04x", c);
                        out += b;
                    } else {
                        out.push_back(static_cast<char>(c));   // UTF-8 原样透传
                    }
            }
        }
        out.push_back('"');
    }

    void write(std::string& out) const {
        switch (kind_) {
            case Kind::Null: out += "null"; break;
            case Kind::Bool: out += bool_ ? "true" : "false"; break;
            case Kind::Number: out += number_to_string(num_); break;
            case Kind::String: escape_into(str_, out); break;
            case Kind::Array: {
                out.push_back('[');
                for (std::size_t i = 0; i < arr_.size(); ++i) {
                    if (i) out.push_back(',');
                    arr_[i].write(out);
                }
                out.push_back(']');
                break;
            }
            case Kind::Object: {
                out.push_back('{');
                for (std::size_t i = 0; i < obj_.size(); ++i) {
                    if (i) out.push_back(',');
                    escape_into(obj_[i].first, out);
                    out.push_back(':');
                    obj_[i].second.write(out);
                }
                out.push_back('}');
                break;
            }
        }
    }

    class Parser {
    public:
        explicit Parser(const std::string& s) : s_(s) {}
        bool eof() const { return i_ >= s_.size(); }
        void skip_ws() {
            while (i_ < s_.size() && (s_[i_] == ' ' || s_[i_] == '\t' ||
                                      s_[i_] == '\n' || s_[i_] == '\r'))
                ++i_;
        }
        Json value() {
            skip_ws();
            if (eof()) throw Error("JSON 意外结束");
            char c = s_[i_];
            if (c == '{') return object();
            if (c == '[') return array();
            if (c == '"') return Json(read_string());
            if (c == 't') { expect("true"); return Json(true); }
            if (c == 'f') { expect("false"); return Json(false); }
            if (c == 'n') { expect("null"); return Json(); }
            return Json(read_number());
        }

    private:
        const std::string& s_;
        std::size_t i_ = 0;

        void expect(const char* word) {
            std::size_t n = std::strlen(word);
            if (s_.compare(i_, n, word) != 0) throw Error(std::string("JSON 期望 ") + word);
            i_ += n;
        }
        Json object() {
            Json j = Json::object();
            ++i_;                                  // '{'
            skip_ws();
            if (!eof() && s_[i_] == '}') { ++i_; return j; }
            for (;;) {
                skip_ws();
                if (eof() || s_[i_] != '"') throw Error("JSON 对象缺少键名");
                std::string key = read_string();
                skip_ws();
                if (eof() || s_[i_] != ':') throw Error("JSON 对象缺少 ':'");
                ++i_;
                j.obj_.emplace_back(std::move(key), value());
                skip_ws();
                if (eof()) throw Error("JSON 对象未闭合");
                if (s_[i_] == ',') { ++i_; continue; }
                if (s_[i_] == '}') { ++i_; return j; }
                throw Error("JSON 对象里出现了意外字符");
            }
        }
        Json array() {
            Json j = Json::array();
            ++i_;                                  // '['
            skip_ws();
            if (!eof() && s_[i_] == ']') { ++i_; return j; }
            for (;;) {
                j.arr_.push_back(value());
                skip_ws();
                if (eof()) throw Error("JSON 数组未闭合");
                if (s_[i_] == ',') { ++i_; continue; }
                if (s_[i_] == ']') { ++i_; return j; }
                throw Error("JSON 数组里出现了意外字符");
            }
        }
        std::string read_string() {
            ++i_;                                  // 起始引号
            std::string out;
            while (true) {
                if (eof()) throw Error("JSON 字符串未闭合");
                char c = s_[i_++];
                if (c == '"') return out;
                if (c != '\\') { out.push_back(c); continue; }
                if (eof()) throw Error("JSON 转义未完成");
                char e = s_[i_++];
                switch (e) {
                    case '"': out.push_back('"'); break;
                    case '\\': out.push_back('\\'); break;
                    case '/': out.push_back('/'); break;
                    case 'n': out.push_back('\n'); break;
                    case 't': out.push_back('\t'); break;
                    case 'r': out.push_back('\r'); break;
                    case 'b': out.push_back('\b'); break;
                    case 'f': out.push_back('\f'); break;
                    case 'u': {
                        unsigned cp = read_hex4();
                        // 代理对 → 合成一个码点
                        if (cp >= 0xD800 && cp <= 0xDBFF && i_ + 1 < s_.size() &&
                            s_[i_] == '\\' && s_[i_ + 1] == 'u') {
                            i_ += 2;
                            unsigned lo = read_hex4();
                            if (lo >= 0xDC00 && lo <= 0xDFFF)
                                cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                        }
                        append_utf8(out, cp);
                        break;
                    }
                    default: throw Error(std::string("JSON 未知转义 \\") + e);
                }
            }
        }
        unsigned read_hex4() {
            if (i_ + 4 > s_.size()) throw Error("JSON \\u 转义不完整");
            unsigned v = 0;
            for (int k = 0; k < 4; ++k) {
                char c = s_[i_++];
                unsigned d;
                if (c >= '0' && c <= '9') d = static_cast<unsigned>(c - '0');
                else if (c >= 'a' && c <= 'f') d = static_cast<unsigned>(c - 'a' + 10);
                else if (c >= 'A' && c <= 'F') d = static_cast<unsigned>(c - 'A' + 10);
                else throw Error("JSON \\u 转义里有非十六进制字符");
                v = (v << 4) | d;
            }
            return v;
        }
        static void append_utf8(std::string& out, unsigned cp) {
            if (cp < 0x80) {
                out.push_back(static_cast<char>(cp));
            } else if (cp < 0x800) {
                out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
                out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
            } else if (cp < 0x10000) {
                out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
                out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
                out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
            } else {
                out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
                out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
                out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
                out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
            }
        }
        double read_number() {
            const char* start = s_.c_str() + i_;
            char* end = nullptr;
            double v = std::strtod(start, &end);
            if (end == start) throw Error("JSON 里出现无法识别的字符");
            i_ += static_cast<std::size_t>(end - start);
            return v;
        }
    };
};

// ══════════════════════════ 引擎调用 ══════════════════════════

using Args = std::initializer_list<std::pair<std::string, Json>>;

namespace detail {

// 缓冲区从 1 MB 起，不够就翻倍（引擎结果可能很长：展开式、矩阵等）
inline std::string raw_call(const std::string& name, const std::string& args_json) {
    std::size_t cap = 1u << 20;
    for (int attempt = 0; attempt < 8; ++attempt, cap *= 2) {
        std::vector<char> buf(cap);
        int n = math_call(name.c_str(), args_json.c_str(), buf.data(),
                          static_cast<int>(cap));
        if (n >= 0) return std::string(buf.data(), static_cast<std::size_t>(n));
    }
    throw Error("引擎调用失败：输出超过缓冲上限，或参数非法（函数：" + name + "）");
}

inline std::string build_args(const Args& args) {
    std::string out = "{";
    bool first = true;
    for (const auto& kv : args) {
        if (!first) out.push_back(',');
        first = false;
        out += Json(kv.first).dump();
        out.push_back(':');
        out += kv.second.dump();
    }
    out.push_back('}');
    return out;
}

}  // namespace detail

/// 引擎是否注册了这个函数。
inline bool exists(const std::string& name) {
    return function_exists(name.c_str());
}

/// 调用引擎，返回完整的 {"isError":...}，**不抛异常**（想自己判错时用）。
inline Json call_raw(const std::string& name, const Args& args = {}) {
    Json out = Json::parse(detail::raw_call(name, detail::build_args(args)));
    return out;
}

/// 调用引擎，返回 value；引擎报错则抛 mfm::Error。
inline Json call(const std::string& name, const Args& args = {}) {
    Json out = Json::parse(detail::raw_call(name, detail::build_args(args)));
    const Json* err = out.find("isError");
    if (err && err->is_bool() && err->as_bool()) {
        const Json* msg = out.find("value");
        throw Error(msg ? (msg->is_string() ? msg->as_string() : msg->dump())
                        : std::string("引擎报错但没给说明"));
    }
    const Json* value = out.find("value");
    if (!value) throw Error("引擎返回里没有 value 字段：" + out.dump());
    return *value;
}

/// 只想要数值时用这个（结果不是数值就抛 Error，比如 ±∞ 返回的是字符串 "oo"）。
inline double num(const std::string& name, const Args& args = {}) {
    Json v = call(name, args);
    if (v.is_number()) return v.as_number();
    throw Error("这次调用的结果不是数值，而是：" + v.dump());
}

/// 只想要文本时用这个（数值会按最少位数格式化，字符串原样返回）。
inline std::string text(const std::string& name, const Args& args = {}) {
    Json v = call(name, args);
    if (v.is_string()) return v.as_string();
    if (v.is_number()) return Json::number_to_string(v.as_number());
    return v.dump();
}

/// 引擎注册的全部函数名。
inline std::vector<std::string> functions() {
    Json v = call("list_functions");
    const Json* list = &v;
    if (v.is_object()) {
        for (const char* key : {"functions", "names", "items"}) {
            const Json* inner = v.find(key);
            if (inner) { list = inner; break; }
        }
    }
    std::vector<std::string> out;
    if (list->is_array())
        for (const Json& item : list->as_array())
            out.push_back(item.is_string() ? item.as_string() : item.dump());
    return out;
}

}  // namespace mfm
