# ⚡ EVN ePoint cho Home Assistant

Tích hợp (custom integration / HACS) đưa dữ liệu điện từ tài khoản **EVN ePoint** (app `EVN ePoint` – `com.icom.epoint`) vào Home Assistant: lịch sử tiêu thụ theo ngày/tháng, lượng điện & **tiền điện tạm tính** tháng này, cùng hóa đơn các kỳ.

> Hoạt động trực tiếp với API ePoint (`api.evnpoint.com`) — **không cần MITM, không cần addon trung gian**. Đăng nhập bằng **số điện thoại + mật khẩu + OTP** y như app.

---

## ✨ Tính năng

1. **Đăng nhập bằng SĐT + mật khẩu**, sau đó **nhập mã OTP** (gửi qua SMS) — ngay trong giao diện thêm tích hợp của Home Assistant.
2. **Danh sách khách hàng / hợp đồng đã liên kết** — mỗi hợp đồng (mã khách hàng) là một *thiết bị* riêng trong HA, kèm tên, địa chỉ, đơn vị điện lực.
3. **Lịch sử sử dụng điện theo ngày & theo tháng** — dạng thuộc tính (attribute) để vẽ biểu đồ.
4. **Lượng điện tiêu thụ hôm nay, tháng này (tạm tính)** và **số tiền tạm tính phải trả**, cùng tiền điện hóa đơn kỳ gần nhất.

### Các cảm biến tạo ra (mỗi hợp đồng)

| Entity | Ý nghĩa | Đơn vị |
|---|---|---|
| `Tiêu thụ hôm nay` | Số điện ngày gần nhất (attr: `daily` = lịch sử theo ngày) | kWh |
| `Tiêu thụ tháng này (tạm tính)` | Ước tính tháng hiện tại (attr: `this_year`/`last_year` theo tháng) | kWh |
| `Tiền điện tạm tính tháng này` | Số tiền tạm tính phải trả (chỉ hợp đồng chính) | VND |
| `Tiêu thụ tháng trước` | Sản lượng tháng liền trước | kWh |
| `Tiền điện hóa đơn gần nhất` | Hóa đơn kỳ gần nhất (attr: `lich_su_hoa_don` = các kỳ) | VND |

---

## 📦 Cài đặt

### Qua HACS (khuyên dùng)
1. HACS → **⋮** → **Custom repositories**.
2. Dán `https://github.com/home-assistant-tools/evn-epoint`, loại **Integration** → **Add**.
3. Tìm **EVN ePoint** → **Download** → **khởi động lại Home Assistant**.

### Thủ công
Copy thư mục `custom_components/evn_epoint` vào `<config>/custom_components/` rồi khởi động lại HA.

---

## ⚙️ Cấu hình

1. **Cài đặt → Thiết bị & Dịch vụ → Thêm tích hợp → "EVN ePoint"**.
2. Nhập **Số điện thoại** + **Mật khẩu** (đúng tài khoản app EVN ePoint).
3. Hệ thống gửi **OTP qua SMS** → nhập mã OTP để hoàn tất.

> Lần đầu là "thiết bị mới" nên bắt buộc có OTP. Token đăng nhập sống ~60 ngày; khi hết hạn HA sẽ tự thử gia hạn, nếu không được sẽ yêu cầu đăng nhập lại (nhập OTP lần nữa).

---

## 📊 Biểu đồ (ApexCharts Card)

Cài `apexcharts-card` qua HACS → Frontend. Thay `sensor.tieu_thu_hom_nay` / `sensor.tieu_thu_thang_nay_tam_tinh` bằng entity thực tế của bạn.

**Tiêu thụ theo ngày:**
```yaml
type: custom:apexcharts-card
header: { show: true, title: Điện tiêu thụ theo ngày }
graph_span: 35d
series:
  - entity: sensor.tieu_thu_hom_nay
    name: kWh/ngày
    type: column
    data_generator: |
      return (entity.attributes.daily || []).map(d => [ new Date(d.date).getTime(), d.kwh ]);
```

**Tiêu thụ theo tháng (năm nay):**
```yaml
type: custom:apexcharts-card
header: { show: true, title: Điện tiêu thụ theo tháng }
graph_span: 1y
span: { start: year }
series:
  - entity: sensor.tieu_thu_thang_nay_tam_tinh
    name: kWh/tháng
    type: column
    data_generator: |
      const ty = entity.attributes.this_year || {};
      return Object.keys(ty).filter(k => /^\d+$/.test(k))
        .map(m => [ new Date(Number(ty.year), Number(m)-1, 1).getTime(), Number(ty[m]) ]);
```

---

## ⚠️ Miễn trừ

Dự án không chính thức, không liên kết với EVN/iCom. Dùng tài khoản EVN ePoint của chính bạn, tự chịu trách nhiệm. Tài khoản chỉ đăng nhập được trên một thiết bị tại một thời điểm — nếu HA đăng nhập, app trên điện thoại có thể bị đăng xuất (và ngược lại).

## 📄 Giấy phép
[MIT](LICENSE)
