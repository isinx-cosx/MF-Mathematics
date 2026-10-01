// json.hpp — 独立 JSON 解析/序列化(仅头文件,零第三方依赖)。
//
// 用法:
//   auto v = mf::json::parse(R"({"n": 10, "xs": [1, 2, 3]})");
//   long long n = v["n"].as_int();
//   std::string s = mf::json::serialize(mf::json::make_object({{"value", 4}}));
//
// 支持 JSON 全部六种值:null / bool / number(int64 或 double) / string /
// array / object。数字若无小数点/指数按 int64 解析,否则按 double。
// 解析失败抛 std::runtime_error。数字类型不匹配抛 std::runtime_error。

#pragma once

#include <cerrno>
#include <charconv>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace mf::json {

class Value;

class Value {
public:
    enum class Type { Null, Bool, Int, Float, String, Array, Object };

    Value() : type_(Type::Null) {}
    Value(std::nullptr_t) : type_(Type::Null) {}
    Value(bool b) : type_(Type::Bool), bool_(b) {}
    Value(std::int64_t i) : type_(Type::Int), int_(i) {}
    Value(int i) : type_(Type::Int), int_(i) {}
    Value(double d) : type_(Type::Float), float_(d) {}
    Value(const char* s) : type_(Type::String), str_(s) {}
    Value(const std::string& s) : type_(Type::String), str_(s) {}

    // 数组:Value{Value(1), Value(2)}  → [1, 2]
    Value(std::initializer_list<Value> init);
    // 对象:Value{{"key", value}, ...} → {"key": value, ...}
    Value(std::initializer_list<std::pair<std::string, Value>> init);

    static Value make_array();                    // 空数组
    static Value make_object();                   // 空对象
    static Value parse(const char* data, std::size_t len);  // 从字节缓冲区解析
    static Value parse(const std::string& s) { return parse(s.data(), s.size()); }

    Type type() const { return type_; }
    bool is_null() const { return type_ == Type::Null; }
    bool is_bool() const { return type_ == Type::Bool; }
    bool is_int() const { return type_ == Type::Int; }
    bool is_number() const { return type_ == Type::Int || type_ == Type::Float; }
    bool is_string() const { return type_ == Type::String; }
    bool is_array() const { return type_ == Type::Array; }
    bool is_object() const { return type_ == Type::Object; }

    bool as_bool() const;
    std::int64_t as_int() const;
    double as_double() const;
    const std::string& as_string() const;

    std::size_t size() const;                      // 数组元素数 / 对象键数
    const Value& at(std::size_t i) const;          // 数组下标访问
    bool has(const std::string& key) const;        // 对象是否含某键
    const Value& operator[](const std::string& key) const;  // 缺键抛异常
    std::vector<std::string> keys() const;         // 对象键(按序)
    void set(const std::string& key, Value v);             // 写入/覆盖对象键
    void push_back(Value v);                               // 追加数组元素

    std::string to_string() const;                 // 序列化为紧凑 JSON

private:
    // 内部构造:解析器从已解析容器直接构建
    explicit Value(std::vector<Value> arr) : type_(Type::Array), arr_(std::move(arr)) {}
    explicit Value(std::map<std::string, Value> obj)
        : type_(Type::Object), obj_(std::move(obj)) {}

    friend class Parser;  // 解析器需构造空数组/空对象

    Type type_ = Type::Null;
    bool bool_ = false;
    std::int64_t int_ = 0;
    double float_ = 0.0;
    std::string str_;
    std::vector<Value> arr_;
    std::map<std::string, Value> obj_;
};

// ── 构造 ─────────────────────────────────────────────────────────────────────

inline Value Value::make_array() { return Value(std::vector<Value>{}); }

inline Value Value::make_object() { return Value(std::map<std::string, Value>{}); }

inline Value::Value(std::initializer_list<Value> init) : type_(Type::Array) {
    arr_.reserve(init.size());
    for (const Value& v : init) arr_.push_back(v);
}

inline Value::Value(std::initializer_list<std::pair<std::string, Value>> init)
    : type_(Type::Object) {
    for (const auto& kv : init) obj_.emplace(kv.first, kv.second);
}

// ── 访问器 ───────────────────────────────────────────────────────────────────

inline bool Value::as_bool() const {
    if (type_ != Type::Bool) throw std::runtime_error("值不是布尔");
    return bool_;
}

inline std::int64_t Value::as_int() const {
    switch (type_) {
        case Type::Int:
            return int_;
        case Type::Float:
            if (float_ >= -9.2233720368547758e18 && float_ <= 9.2233720368547758e18 &&
                float_ == static_cast<double>(static_cast<std::int64_t>(float_))) {
                return static_cast<std::int64_t>(float_);
            }
            throw std::runtime_error("浮点值无法转为整数");
        default:
            throw std::runtime_error("值不是数字");
    }
}

inline double Value::as_double() const {
    switch (type_) {
        case Type::Int:
            return static_cast<double>(int_);
        case Type::Float:
            return float_;
        default:
            throw std::runtime_error("值不是数字");
    }
}

inline const std::string& Value::as_string() const {
    if (type_ != Type::String) throw std::runtime_error("值不是字符串");
    return str_;
}

inline std::size_t Value::size() const {
    if (type_ == Type::Array) return arr_.size();
    if (type_ == Type::Object) return obj_.size();
    throw std::runtime_error("值不是数组或对象");
}

inline const Value& Value::at(std::size_t i) const {
    if (type_ != Type::Array) throw std::runtime_error("值不是数组");
    if (i >= arr_.size()) throw std::runtime_error("数组下标越界");
    return arr_[i];
}

inline bool Value::has(const std::string& key) const {
    if (type_ != Type::Object) throw std::runtime_error("值不是对象");
    return obj_.count(key) != 0;
}

inline const Value& Value::operator[](const std::string& key) const {
    if (type_ != Type::Object) throw std::runtime_error("值不是对象");
    auto it = obj_.find(key);
    if (it == obj_.end()) throw std::runtime_error("对象缺少键: " + key);
    return it->second;
}

inline void Value::push_back(Value v) {
    if (type_ == Type::Null) type_ = Type::Array;
    if (type_ != Type::Array) throw std::runtime_error("push_back 只能用于数组");
    arr_.push_back(std::move(v));
}

inline void Value::set(const std::string& key, Value v) {
    if (type_ == Type::Null) type_ = Type::Object;
    if (type_ != Type::Object) throw std::runtime_error("set 只能用于对象");
    obj_[key] = std::move(v);
}

inline std::vector<std::string> Value::keys() const {
    if (type_ != Type::Object) throw std::runtime_error("值不是对象");
    std::vector<std::string> out;
    out.reserve(obj_.size());
    for (const auto& kv : obj_) out.push_back(kv.first);
    return out;
}

// ── 序列化 ───────────────────────────────────────────────────────────────────

namespace detail {

inline void append_escaped(std::string& out, const std::string& s) {
    out.push_back('"');
    for (char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            case '\b': out += "\\b";  break;
            case '\f': out += "\\f";  break;
            default:   out.push_back(c); break;
        }
    }
    out.push_back('"');
}

inline void append_double(std::string& out, double d) {
    if (d != d) { out += "null"; return; }  // NaN
    if (d == std::numeric_limits<double>::infinity() ||
        d == -std::numeric_limits<double>::infinity()) {
        out += "null";  // ±inf
        return;
    }
    if (d >= -9.2233720368547758e18 && d <= 9.2233720368547758e18 &&
        d == static_cast<double>(static_cast<std::int64_t>(d))) {
        out += std::to_string(static_cast<std::int64_t>(d));
        return;
    }
    // 最短往返表示(同 Python repr),避免 %.17g 的尾零噪声
    char buf[40];
    const auto res = std::to_chars(buf, buf + sizeof(buf), d,
                                   std::chars_format::general);
    out.append(buf, res.ptr);
}

}  // namespace detail

inline std::string Value::to_string() const {
    std::string out;
    switch (type_) {
        case Type::Null:   out += "null"; break;
        case Type::Bool:   out += bool_ ? "true" : "false"; break;
        case Type::Int:    out += std::to_string(int_); break;
        case Type::Float:  detail::append_double(out, float_); break;
        case Type::String: detail::append_escaped(out, str_); break;
        case Type::Array: {
            out.push_back('[');
            for (std::size_t i = 0; i < arr_.size(); ++i) {
                if (i) out.push_back(',');
                out += arr_[i].to_string();
            }
            out.push_back(']');
            break;
        }
        case Type::Object: {
            out.push_back('{');
            bool first = true;
            for (const auto& kv : obj_) {
                if (!first) out.push_back(',');
                first = false;
                detail::append_escaped(out, kv.first);
                out.push_back(':');
                out += kv.second.to_string();
            }
            out.push_back('}');
            break;
        }
    }
    return out;
}

// ── 解析 ─────────────────────────────────────────────────────────────────────

class Parser {
public:
    Parser(const char* data, std::size_t len) : s_(data), n_(len) {}

    Value parse_root() {
        skip_ws();
        Value v = parse_value();
        skip_ws();
        if (pos_ < n_) throw err("表达式后存在多余字符");
        return v;
    }

private:
    const char* s_;
    std::size_t n_;
    std::size_t pos_ = 0;

    std::runtime_error err(const std::string& msg) const {
        return std::runtime_error("JSON 解析错误: " + msg + " (位置 " +
                                  std::to_string(pos_) + ")");
    }

    bool has(std::size_t k) const { return pos_ + k <= n_; }

    char peek(std::size_t k = 0) const {
        return pos_ + k < n_ ? s_[pos_ + k] : '\0';
    }

    void skip_ws() {
        while (pos_ < n_ && (s_[pos_] == ' ' || s_[pos_] == '\t' ||
                             s_[pos_] == '\n' || s_[pos_] == '\r')) ++pos_;
    }

    void expect(char c) {
        if (!has(0) || s_[pos_] != c) throw err(std::string("缺少字符 '") + c + "'");
        ++pos_;
    }

    Value parse_value() {
        if (!has(0)) throw err("意外的文件结束");
        switch (s_[pos_]) {
            case '{': return parse_object();
            case '[': return parse_array();
            case '"': return Value(parse_string());
            case 't': consume_lit("true");  return Value(true);
            case 'f': consume_lit("false"); return Value(false);
            case 'n': consume_lit("null");  return Value(nullptr);
            case 'I': consume_lit("Infinity");  return Value(std::numeric_limits<double>::infinity());
            case 'N': consume_lit("NaN");       return Value(std::numeric_limits<double>::quiet_NaN());
            default:
                if (s_[pos_] == '-' && has(1) && s_[pos_ + 1] == 'I') {
                    consume_lit("-Infinity");
                    return Value(-std::numeric_limits<double>::infinity());
                }
                if (s_[pos_] == '-' || (s_[pos_] >= '0' && s_[pos_] <= '9')) return parse_number();
                throw err(std::string("未预期的字符 '") + s_[pos_] + "'");
        }
    }

    void consume_lit(const char* lit) {
        std::size_t i = 0;
        while (lit[i]) {
            if (!has(i) || s_[pos_ + i] != lit[i])
                throw err(std::string("非法字面量,期望 '") + lit + "'");
            ++i;
        }
        pos_ += i;
    }

    Value parse_object() {
        expect('{');
        std::map<std::string, Value> obj;
        skip_ws();
        if (peek() == '}') { ++pos_; return Value(std::move(obj)); }
        for (;;) {
            skip_ws();
            if (peek() != '"') throw err("对象键必须为字符串");
            std::string key = parse_string();
            skip_ws();
            expect(':');
            skip_ws();
            obj.emplace(std::move(key), parse_value());
            skip_ws();
            char c = peek();
            if (c == ',') { ++pos_; continue; }
            if (c == '}') { ++pos_; break; }
            throw err("对象内应为 ',' 或 '}'");
        }
        return Value(std::move(obj));
    }

    Value parse_array() {
        expect('[');
        std::vector<Value> arr;
        skip_ws();
        if (peek() == ']') { ++pos_; return Value(std::move(arr)); }
        for (;;) {
            skip_ws();
            arr.push_back(parse_value());
            skip_ws();
            char c = peek();
            if (c == ',') { ++pos_; continue; }
            if (c == ']') { ++pos_; break; }
            throw err("数组内应为 ',' 或 ']'");
        }
        return Value(std::move(arr));
    }

    std::string parse_string() {
        expect('"');
        std::string out;
        for (;;) {
            if (pos_ >= n_) throw err("字符串未闭合");
            char c = s_[pos_++];
            if (c == '"') break;
            if (c == '\\') {
                if (pos_ >= n_) throw err("转义序列不完整");
                char e = s_[pos_++];
                switch (e) {
                    case '"':  out.push_back('"');  break;
                    case '\\': out.push_back('\\'); break;
                    case '/':  out.push_back('/');  break;
                    case 'b':  out.push_back('\b'); break;
                    case 'f':  out.push_back('\f'); break;
                    case 'n':  out.push_back('\n'); break;
                    case 'r':  out.push_back('\r'); break;
                    case 't':  out.push_back('\t'); break;
                    case 'u': parse_unicode_escape(out); break;
                    default: throw err("未知转义符 '\\" + std::string(1, e) + "'");
                }
            } else if (static_cast<unsigned char>(c) < 0x20) {
                throw err("字符串含未转义控制字符");
            } else {
                out.push_back(c);
            }
        }
        return out;
    }

    // 解析 \uXXXX 并追加 UTF-8 编码
    void parse_unicode_escape(std::string& out) {
        if (!has(4)) throw err("\\u 转义不完整");
        char hex[5] = {s_[pos_], s_[pos_ + 1], s_[pos_ + 2], s_[pos_ + 3], '\0'};
        pos_ += 4;
        char* end = nullptr;
        long cp = std::strtol(hex, &end, 16);
        if (end != hex + 4) throw err("\\u 转义不是合法 16 进制");
        // 仅处理 BMP,足够本库使用;代理对不做合并
        if (cp < 0x80) {
            out.push_back(static_cast<char>(cp));
        } else if (cp < 0x800) {
            out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else {
            out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        }
    }

    Value parse_number() {
        std::size_t start = pos_;
        bool is_float = false;
        if (peek() == '-') ++pos_;
        if (!has(0) || !(s_[pos_] >= '0' && s_[pos_] <= '9'))
            throw err("无效的数字");
        while (pos_ < n_ && s_[pos_] >= '0' && s_[pos_] <= '9') ++pos_;
        if (peek() == '.') {
            is_float = true;
            ++pos_;
            if (!has(0) || !(s_[pos_] >= '0' && s_[pos_] <= '9'))
                throw err("小数点后缺少数字");
            while (pos_ < n_ && s_[pos_] >= '0' && s_[pos_] <= '9') ++pos_;
        }
        if (peek() == 'e' || peek() == 'E') {
            is_float = true;
            ++pos_;
            if (peek() == '+' || peek() == '-') ++pos_;
            if (!has(0) || !(s_[pos_] >= '0' && s_[pos_] <= '9'))
                throw err("指数部分缺少数字");
            while (pos_ < n_ && s_[pos_] >= '0' && s_[pos_] <= '9') ++pos_;
        }
        std::string tok(s_ + start, pos_ - start);
        if (!is_float) {
            errno = 0;
            char* end = nullptr;
            long long val = std::strtoll(tok.c_str(), &end, 10);
            if (errno == 0 && end == tok.c_str() + tok.size()) return Value(val);
            // 超出 int64 范围,降级 double
        }
        return Value(std::strtod(tok.c_str(), nullptr));
    }
};

inline Value Value::parse(const char* data, std::size_t len) {
    Parser p(data, len);
    return p.parse_root();
}

}  // namespace mf::json
