# Phiếu Phản Ánh — K4 Ngày 12

> **Bài làm cá nhân.** Trả lời bằng lời của chính bạn, dựa trên những gì bạn
> quan sát được khi chạy code — không sao chép đáp án của người khác.
>
> Họ và tên: Nguyễn Hoàng Thảo Tiên  Mã học viên: 2A202601650

---

### Câu 1 — Fail fast (CP1)

Trong `Settings`, `api_token` không có giá trị mặc định nên app chết ngay khi
khởi động nếu thiếu biến môi trường. Hãy mô tả một tình huống cụ thể mà việc
"chết sớm" này cứu bạn, so với việc để mặc định `"changeme"`.

Tình huống: tôi deploy lên Railway, tạo service từ Dockerfile, nhưng khi điền
biến môi trường thì gõ sai tên — `API-TOKEN` thay vì `API_TOKEN`.

- **Có mặc định `"changeme"`**: container khởi động bình thường, `/healthz` trả
  200, dashboard hiện màu xanh, tôi tick xong CP5 và đi làm việc khác. Service
  lúc này nhận đúng một token duy nhất là chuỗi `changeme` — chuỗi mà mọi người
  đọc source trên GitHub đều biết, và repo của tôi thì public. Bất kỳ ai cũng
  gọi được `/chat`. Tôi chỉ phát hiện ra khi hóa đơn LLM tăng bất thường hoặc
  khi cost guard bắt đầu trả 402 cho những `client_id` tôi chưa từng thấy —
  tức là sau khi thiệt hại đã xảy ra rồi.
- **Không có mặc định**: `Settings()` raise `ValidationError` ngay lúc import
  `app.config`, uvicorn không lên được, container chết. Railway thấy health
  check không bao giờ pass nên giữ lại bản cũ và đánh dấu deploy thất bại. Tôi
  mở log, thấy đúng dòng `api_token Field required`, sửa tên biến, deploy lại.
  Tổng thiệt hại: 2 phút, và không có một giây nào service chạy ở trạng thái
  không an toàn.

Điểm cốt lõi: sai cấu hình là chuyện sẽ xảy ra, không phải chuyện có thể xảy
ra. Câu hỏi duy nhất là nó biểu hiện thành *một lỗi ồn ào lúc khởi động* hay
*một lỗ hổng im lặng lúc đang chạy*. Giá trị mặc định cho secret chính là thứ
biến trường hợp đầu thành trường hợp sau.

---

### Câu 2 — Log cho máy đọc (CP1)

Chạy service và gọi `/chat` vài lần. Dán một dòng log JSON bạn thu được, rồi
nêu **hai** việc bạn làm được với dòng log đó mà `print("đã trả lời xong")`
không làm được.

Dòng log thật lấy từ `docker compose logs chat`:

```json
{"event": "chat_completed", "severity": "INFO", "ts": "2026-08-10T07:45:42.032672+00:00", "client_id": "sv-rl", "prompt_tokens": 269, "completion_tokens": 43, "usd_cost": 6.615e-05}
```

**Việc 1 — cộng tiền theo từng client mà không cần thêm hạ tầng gì.** Vì
`usd_cost` và `client_id` là *field* chứ không phải chữ trong câu, tôi lọc và
cộng dồn được ngay trên log:

```bash
docker compose logs chat --no-log-prefix | grep '^{' \
  | jq -s 'map(select(.event=="chat_completed"))
           | group_by(.client_id)
           | map({client: .[0].client_id, usd: (map(.usd_cost) | add)})'
```

Tôi chạy lệnh này và ra được tổng chi phí từng `client_id` của phiên vừa rồi.
Với `print("đã trả lời xong")` thì thông tin đó đơn giản là không tồn tại —
không có gì để cộng.

**Việc 2 — đặt cảnh báo theo điều kiện số học.** Trên Cloud Logging hay
Datadog tôi viết được filter kiểu `severity >= ERROR` hoặc
`jsonPayload.usd_cost > 0.01`, gắn vào một alert policy. Điều kiện đó chạy được
vì `severity` là khóa chuẩn (nên tôi viết hoa nó) và `usd_cost` là số. Với log
dạng câu, muốn làm điều tương tự tôi phải viết regex bám vào cách diễn đạt của
chính mình — và regex đó vỡ ngay lần đầu ai đó sửa lại câu thông báo.

Một chi tiết nữa tôi mới thấy giá trị: mỗi event **một dòng**. Cloud gom log
theo dòng, nên nếu tôi dùng `json.dumps(..., indent=2)` thì một event thành 8
bản ghi rác, không bản ghi nào parse được. Và `print(..., flush=True)` là cần
thiết vì stdout trong container bị buffer — không flush thì log của những giây
cuối trước khi crash biến mất, đúng lúc tôi cần nó nhất.

---

### Câu 3 — Kích thước image (CP2)

Build cả hai phiên bản và ghi lại số đo thật:

```bash
docker build -f Dockerfile.single -t chat:single .
docker build -t day12-chat:prod .
docker images | grep chat
```

| Bản | Dung lượng |
|-----|-----------|
| 1 stage (bản đầu, `FROM python:3.11`) | 1730 MB (1.73 GB) |
| Multi-stage (`python:3.11-slim`) | 334 MB |

Giảm 1396 MB, còn khoảng **19%** so với bản đầu. Phần chênh lệch gồm hai nhóm,
và nhóm lớn hơn không phải nhóm tôi đoán ban đầu:

1. **Base image (~1.2 GB).** `python:3.11` dựng trên Debian bản đầy đủ và mang
   theo cả một toolchain: `gcc`, `g++`, `make`, header của libc, Git,
   Subversion, Mercurial, `imagemagick`... Đó là những thứ để *build* thư viện
   có phần C, không phải để *chạy* app. `python:3.11-slim` bỏ hết, chỉ giữ
   Python và vài lib runtime — khoảng 130 MB.
2. **Rác của build và của repo (~150 MB).** Bản một stage `COPY . .` trước khi
   `pip install`, nên nó copy luôn `.git`, `.venv` của máy tôi (còn sai kiến
   trúc vì tôi build image Linux từ máy macOS), `tests/`, `screenshots/`,
   `__pycache__`, cộng với cache của `pip` nằm lại trong layer. Bản multi-stage
   chỉ `COPY app/` và `utils/`, và `.dockerignore` chặn phần còn lại.

Điều tôi thấy đáng chú ý: `RUN pip install` ở stage `builder` vẫn tải và biên
dịch đủ mọi thứ, cache của nó vẫn phình ra — nhưng toàn bộ chuyện đó xảy ra
trong một stage bị **bỏ đi**. Stage runtime chỉ `COPY --from=builder
/opt/venv`, tức là chỉ lấy kết quả cuối. Đó là lý do multi-stage hiệu quả hơn
việc đi dọn dẹp bằng `rm -rf` trong cùng một layer: layer đã ghi thì xóa cũng
không lấy lại được dung lượng, chỉ multi-stage mới thật sự không mang nó theo.

Con số 334 MB vẫn hơi cao so với mức có thể đạt được, vì `requirements.txt`
gộp cả `pytest`, `fakeredis`, `httpx`, `PyYAML` — đều là thư viện chỉ dùng để
test. Tách thành `requirements.txt` và `requirements-dev.txt` thì image còn
xuống được nữa.

---

### Câu 4 — Thứ tự lệnh trong Dockerfile (CP2)

Sửa một ký tự trong `app/main.py` rồi build lại. Với Dockerfile của bạn, những
layer nào được dùng lại từ cache, layer nào phải chạy lại? Nếu bạn đặt
`COPY . .` lên trước `RUN pip install` thì kết quả khác thế nào?

Tôi thêm một ký tự vào `app/main.py` rồi chạy `docker build --progress=plain`.
Output thật:

```
#6  [builder 4/5] COPY requirements.txt ./            CACHED
#7  [builder 3/5] RUN python -m venv /opt/venv        CACHED
#8  [runtime 3/6] WORKDIR /app                        CACHED
#9  [runtime 2/6] RUN useradd --uid 10001 appuser     CACHED
#10 [builder 5/5] RUN pip install -r requirements.txt CACHED   ← quan trọng nhất
#12 [runtime 4/6] COPY --from=builder /opt/venv       CACHED
#13 [runtime 5/6] COPY app/ ./app/                    (chạy lại)
#14 [runtime 6/6] COPY utils/ ./utils/                (chạy lại)
```

Nghĩa là: **mọi layer đều hit cache trừ hai lệnh `COPY` source cuối cùng.**
Build lần hai xong trong khoảng một giây; cả bước cài dependency lẫn bước copy
virtualenv 300 MB đều không phải làm lại.

Lý do: Docker cache theo layer, và một layer chỉ hợp lệ khi *lệnh của nó* và
*mọi layer trước nó* không đổi. Với `COPY`, "không đổi" được xác định bằng
checksum nội dung file được copy. `requirements.txt` tôi không sửa nên layer #6
còn nguyên, kéo theo `RUN pip install` ở #10 cũng còn nguyên. Điều thay đổi
duy nhất là nội dung `app/`, nên vết nứt chỉ bắt đầu từ #13 — đúng chỗ tôi
muốn, vì đó là layer nhỏ nhất (vài chục KB).

Nếu đặt `COPY . .` **trước** `RUN pip install`: checksum của layer `COPY` đổi
mỗi lần tôi sửa bất kỳ file nào trong repo — kể cả sửa README hay thêm một
screenshot. Layer đó vô hiệu, và vì `RUN pip install` nằm *sau* nó nên nó cũng
mất cache theo, dù `requirements.txt` không thay đổi một byte. Kết quả: tải và
cài lại toàn bộ thư viện từ đầu, mỗi lần sửa một dòng code. Bản một stage ban
đầu chính là kiểu đó, và tôi đo được nó mất khoảng 2 phút cho mỗi lần build,
so với ~1 giây.

Quy tắc tôi rút ra: **xếp các lệnh trong Dockerfile theo tần suất thay đổi,
ít đổi lên trên.** Base image ít đổi nhất → `requirements.txt` (đổi vài lần
một tháng) → source code (đổi vài chục lần một ngày) xuống cuối.

---

### Câu 5 — Vì sao không chạy bằng root (CP2)

Container mặc định chạy bằng root. Mô tả chuỗi sự kiện dẫn từ "một lỗ hổng
trong code Python của bạn" tới "kẻ tấn công có quyền cao trên máy host", và
lệnh `USER` cắt đứt chuỗi đó ở chỗ nào.

Chuỗi sự kiện:

1. **Có lỗ hổng trong app.** Ví dụ tôi thêm một endpoint nhận tên file rồi
   `open(path)` mà không kiểm tra, hoặc một thư viện trong `requirements.txt`
   có CVE cho phép thực thi code khi deserialize. Kẻ tấn công gửi request và
   chạy được lệnh tùy ý, nhưng *bên trong* container.
2. **Leo quyền trong container.** Nếu process là root (uid 0), họ đọc được
   `/proc/self/environ` để lấy `API_TOKEN`, ghi vào `/etc/`, cài thêm công cụ
   bằng `apt-get`, sửa code Python trong `/app` để cắm backdoor tồn tại qua
   các request sau. Là user thường thì phần lớn những việc này báo
   `Permission denied`.
3. **Thoát ra host.** Đây là bước cần root. uid trong container và uid trên
   host là **cùng một không gian số** — kernel chỉ có một bảng uid, namespace
   chỉ là lớp che. Vì vậy root-trong-container = uid 0 trên host. Từ đó, chỉ
   cần một điểm tựa là ra ngoài được:
   - volume mount: `-v /var/run/docker.sock:...` (khá phổ biến trong CI) cho
     phép tạo container mới với `--privileged` → toàn quyền host;
   - `-v /host/path:/data`: ghi file trên host với quyền root, ví dụ thêm khóa
     SSH vào `/root/.ssh/authorized_keys`;
   - một CVE escape của runc/kernel: gần như tất cả đều yêu cầu uid 0 và một
     capability mà chỉ root có (`CAP_SYS_ADMIN`, `CAP_DAC_OVERRIDE`...).
4. **Có quyền cao trên host.** Từ đây họ sang được các container khác, đọc
   secret của toàn bộ cụm.

`USER appuser` cắt chuỗi ở **bước 3, và làm bước 2 khó hơn nhiều**. Process
chạy dưới uid 10001, một uid không có ý nghĩa gì trên host: nó không sở hữu
file nào, không có capability nào, không mở được Docker socket kể cả khi socket
bị mount vào. Kẻ tấn công vẫn chạy được code trong container (bước 1 vẫn
thành công — `USER` không sửa lỗ hổng), nhưng thiệt hại bị đóng khung trong
container đó thay vì lan ra cả máy. Tôi kiểm tra lại bằng:

```
$ docker compose exec chat id
uid=10001(appuser) gid=10001(appuser) groups=10001(appuser)
```

Đây là nguyên tắc *defense in depth*: giả định lớp trước sẽ bị chọc thủng, và
lo sẵn việc giới hạn hậu quả. `USER` chỉ là một dòng, nhưng nó biến "mất cả
máy chủ" thành "mất một container mà orchestrator sẽ restart".

---

### Câu 6 — Bearer token (CP3)

Vì sao 401 phải kèm header `WWW-Authenticate: Bearer`? Và vì sao ta trả **cùng
một** thông báo lỗi cho cả ba trường hợp (thiếu header, sai scheme, sai token)
thay vì nói rõ sai ở đâu cho người dùng dễ sửa?

**Về `WWW-Authenticate`.** RFC 7235 quy định response 401 **phải** có header
này; thiếu nó thì đúng nghĩa là response sai chuẩn HTTP. Mục đích: 401 chỉ nói
"bạn chưa được xác thực", còn `WWW-Authenticate` nói "và đây là cách xác
thực". Có nó thì client tự xử lý được mà không cần đọc tài liệu của tôi:

- `httpx`/`requests` với `auth=...`, hay các HTTP client sinh từ OpenAPI, dựa
  vào header này để biết nên gắn `Authorization: Bearer` chứ không phải
  `Basic` hay ký OAuth;
- trình duyệt phân biệt `Basic` (bật hộp thoại đăng nhập) với `Bearer` (không
  bật, vì token không phải thứ người dùng gõ tay);
- proxy và API gateway dùng nó để biết đây là lỗi xác thực chứ không phải lỗi
  ngẫu nhiên, nên không retry vô nghĩa.

Nếu sau này tôi đổi sang JWT có scope, tôi mở rộng thành
`WWW-Authenticate: Bearer error="insufficient_scope"` và client cũ vẫn hiểu.
Trong bài, tôi kiểm tra lại bằng curl và thấy đúng `www-authenticate: Bearer`
trong response 401.

**Về việc dùng chung một thông báo.** Vì thông báo lỗi chi tiết chỉ hữu ích cho
người *đã có* token đúng — mà người đó thì không gặp 401. Người thật sự đọc
từng dòng 401 là người đang dò. Nếu tôi phân biệt:

- `"missing Authorization header"` → xác nhận endpoint này có xác thực;
- `"unsupported scheme, use Bearer"` → cho biết chính xác dạng token;
- `"invalid token"` → **đây là dòng đắt nhất**: nó xác nhận định dạng token đã
  đúng, chỉ sai giá trị. Kẻ dò biết mình đang đi đúng hướng và tiếp tục.

Ba thông báo khác nhau là một *oracle*: mỗi lần thử, kẻ tấn công thu được một
bit thông tin. Một thông báo duy nhất `"invalid or missing bearer token"` cho
họ đúng số 0 bit — thử 10.000 lần vẫn không biết mình sai ở đâu.

Cùng logic đó là lý do tôi dùng `secrets.compare_digest` thay cho `==`. Toán
tử `==` dừng ở ký tự đầu tiên khác nhau, nên token sai từ ký tự thứ 20 so lâu
hơn token sai từ ký tự đầu. Chênh lệch cỡ nanosecond, nhưng lặp lại vài nghìn
lần và lấy trung bình thì nó nổi lên trên nhiễu mạng, và kẻ tấn công dò được
token theo từng ký tự — độ phức tạp từ 64^43 xuống còn 64×43.
`compare_digest` luôn chạy hết chuỗi nên thời gian không phụ thuộc nội dung.
Bịt kỹ thông báo lỗi rồi mà để hở kênh thời gian thì cũng bằng không.

---

### Câu 7 — Token bucket (CP3)

Với `capacity=10`, `refill_per_minute=10`: một client im lặng 10 phút rồi gửi
liên tiếp. Nó gửi được bao nhiêu request trước khi bị 429? Nếu bỏ đoạn
`min(capacity, ...)` trong `available()` thì con số đó thành bao nhiêu, và tại sao?

**Có `min(capacity, ...)`: 10 request, request thứ 11 trả 429.**

Trong 10 phút im lặng, xô tích thêm `600s × (10/60) = 100` token. Nhưng
`available()` kết thúc bằng `min(float(self.capacity), tokens)`, nên 100 bị kẹp
xuống 10 — sức chứa của xô. Client tiêu 10 token liên tiếp; ở lần thứ 11,
`available()` trả một giá trị nhỏ hơn 1 nên `consume()` raise 429 kèm
`Retry-After: 7` (khoảng 6 giây nữa mới có token tiếp theo, làm tròn lên).

Tôi đo lại bằng 15 request liên tiếp cùng một `X-Client-Id` qua compose:

```
200 200 200 200 200 200 200 200 200 200 429 429 429 429 429
```

Đúng 10 rồi 429 — khớp với `capacity=10`.

**Bỏ `min(capacity, ...)`: 100 request, request thứ 101 mới bị 429.**

Không có mức kẹp, `tokens` cộng dồn tuyến tính theo thời gian im lặng và không
có trần. Im lặng 10 phút → 100 token → bắn được 100 request liên tiếp. Im lặng
một ngày → `86400 × (10/60) = 14.400` token → 14.400 request trong một giây,
nếu mạng cho phép.

Điều đó phá đúng thứ mà rate limit tồn tại để bảo vệ: **tốc độ tức thời**.
Trung bình 10 request/phút vẫn được giữ đúng, nhưng service không sập vì trung
bình — nó sập vì 14.400 request đến trong cùng một giây. Và kẻ muốn tấn công
không cần làm gì tinh vi: chỉ cần *chờ*. Càng im lặng lâu càng bắn được nhiều,
tức là hệ thống tự thưởng cho việc tích lũy đạn.

`capacity` chính là tham số "cho phép bùng bao nhiêu", `refill_per_minute` là
tham số "tốc độ bền vững bao nhiêu". Bỏ `min()` đi thì tham số thứ nhất mất
tác dụng, và cái còn lại không đủ để bảo vệ gì cả.

---

### Câu 8 — Ngân sách theo ngày (CP3)

So sánh hạn mức $30/tháng với hạn mức $1/ngày cho cùng một client. Giả sử có sự
cố khiến một client gọi liên tục từ 2h sáng. Với mỗi cách, thiệt hại tối đa là
bao nhiêu và service tự hồi phục khi nào?

Hai hạn mức có cùng "tổng ngân sách một tháng" nhưng khác nhau hoàn toàn ở
hình dạng rủi ro.

| | $30/tháng | $1/ngày |
|---|---|---|
| Thiệt hại tối đa của một sự cố | **$30** — cạn cả tháng trong một đêm | **$1** |
| Service hồi phục khi nào | 00:00 ngày 1 tháng sau (có thể tới 30 ngày) | 00:00 UTC hôm sau, tối đa ~22 giờ |
| Ai phải can thiệp | tôi, bằng tay: nâng hạn mức hoặc chờ hết tháng | không ai, key Redis đổi theo ngày |
| Lúc tôi biết chuyện | khi tiền đã mất phần lớn | khi mất $1 |

**Với $30/tháng.** Sự cố bắt đầu 2h sáng ngày 3. Client bắn liên tục; rate
limit giữ tốc độ ở 10 request/phút nhưng không giữ *tiền*, và mỗi request có
thể là 50k token. Đến khoảng 4h sáng ngân sách cạn, `check()` bắt đầu trả 402.
Tôi ngủ, 8h sáng mới thấy. Lúc đó: mất $30, và service **vẫn đang trả 402 cho
mọi client** cho tới hết ngày 30 — nghĩa là một client hỏng làm 28 ngày còn
lại của tháng không dùng được. Bắt buộc phải can thiệp tay.

**Với $1/ngày.** Cùng sự cố, đến khoảng 2h05 thì `spent()` vượt $1 và client
đó nhận 402. Thiệt hại: $1. Đúng 00:00 UTC, `CostGuard.today()` trả nhãn ngày
mới nên `_key()` trỏ sang một key Redis khác, `spent()` đọc key chưa tồn tại →
trả `0.0` → client được phục vụ lại. Không có cron job, không có ai bấm reset:
việc hồi phục là *hệ quả của cách đặt tên key*, và tôi thấy đó là phần thanh
lịch nhất của thiết kế này.

Nếu sự cố chưa được sửa thì hôm sau nó lại đốt $1 nữa. Nhưng đó lại là điểm
tốt: tôi có một chuỗi sự kiện lặp lại đủ nhỏ để không đau và đủ đều để nhìn
thấy trên log, thay vì một cú $30 rồi im lặng cả tháng.

Hai điều tôi vẫn phải nhớ:

1. Hạn mức là **theo từng client** (`spend:<client_id>:<ngày>`). 200 client
   hỏng cùng lúc thì tổng phơi nhiễm là $200/ngày, không phải $1. Muốn chặn
   thật thì cần thêm một hạn mức toàn cục.
2. `check()` được gọi *trước* `generate_reply()`, và ở bài này gọi với
   `estimated_cost=0.0` — nên request cuối cùng vẫn được đi qua và có thể vượt
   trần một chút. Muốn chặt hơn thì truyền chi phí ước lượng theo độ dài prompt
   vào `estimated_cost`. Đây là đánh đổi có ý thức, không phải sơ suất: chặn
   sau khi đã gọi LLM thì vừa mất tiền vừa trả lỗi.

---

### Câu 9 — /healthz khác /readyz (CP4)

Nếu gộp hai endpoint làm một và cho nó kiểm tra Redis, chuyện gì xảy ra với cụm
3 container khi Redis mất kết nối 30 giây? Trả lời theo đúng thứ tự sự kiện.

Giả sử cả liveness probe và readiness probe đều trỏ vào một endpoint có gọi
`store.ping()`. Redis mất kết nối lúc `t=0`.

1. **t=0** — Redis không trả lời. Ba container vẫn sống, vẫn phục vụ được
   `/healthz`, vẫn giữ nguyên request đang xử lý.
2. **t≈0–10s** — Lượt probe tiếp theo của cả ba container gọi `ping()`, nhận
   `False`, trả 503. Với cấu hình của tôi (`interval: 10s`, `retries: 3`) thì
   khoảng ba nhịp probe là chạm ngưỡng.
3. **t≈10s** — Load balancer thấy 503 và rút cả ba instance ra khỏi vòng xoay.
   **Không còn backend nào.** Người dùng nhận 502/503 cho mọi request — kể cả
   những request không cần Redis.
4. **t≈30s** — Liveness cũng đã fail đủ số lần, orchestrator kết luận "process
   hỏng, phải restart" và giết cả ba container **cùng lúc**. Mọi request đang
   xử lý dở bị cắt giữa chừng. Toàn bộ warm state (kết nối, cache của
   interpreter) mất sạch.
5. **t≈30s** — Đúng lúc này Redis hồi phục. Nhưng ba container mới đang trong
   giai đoạn khởi động lạnh: pull/start, import Python, uvicorn lên, chờ
   `start_period`. Mất thêm 10–30 giây nữa mới có instance đầu tiên trả 200.
6. **t≈40–60s** — Cụm mới thật sự phục vụ lại.

Kết quả: **Redis chết 30 giây, nhưng người dùng mất dịch vụ 40–60 giây** — dài
hơn cả sự cố gốc. Tệ hơn: nếu Redis chết lâu hơn thời gian khởi động, hệ thống
vào **crash loop** — container mới lên, probe fail vì Redis vẫn chết, bị giết,
lên lại... Orchestrator bắt đầu backoff theo hàm mũ, và khi Redis quay lại thì
cụm còn phải chờ hết backoff mới được lên. Restart không sửa được gì cả, vì
lỗi không nằm trong container.

Tách hai endpoint thì cùng sự cố diễn ra thế này: `/readyz` trả 503 → LB
ngừng đẩy traffic mới (đúng, vì `/chat` cần Redis); `/healthz` vẫn trả 200 →
**không container nào bị restart**; t=30s Redis lên, nhịp probe sau đó
`/readyz` trả 200 → LB đưa cả ba instance trở lại ngay. Tổng gián đoạn ≈ 30
giây, đúng bằng sự cố, và không có khởi động lạnh.

Hai probe trả lời hai câu hỏi khác nhau, và đó là lý do chúng phải là hai
endpoint:

- `/healthz` → *"container này có hỏng đến mức phải restart không?"* Chỉ được
  fail khi restart **là** cách sửa. Redis chết thì restart không sửa được gì.
- `/readyz` → *"có nên gửi request vào instance này lúc này không?"* Được phép
  fail vì lý do bên ngoài, vì hậu quả chỉ là tạm ngừng nhận traffic — hồi phục
  tức thì, không mất mát.

Đây cũng là lý do trong `main.py` tôi khai báo `def healthz()` **không có tham
số dependency nào**, còn `readyz` thì nhận `store: ChatStore = Depends(...)`.
Sự khác biệt đó nằm ngay ở chữ ký hàm, không phải trong tài liệu — và test
`test_healthz_khong_phu_thuoc_dependency_nao` kiểm tra đúng điều này bằng
`inspect.signature`.

---

### Câu 10 — Deploy thật (CP5)

Ghi lại **một** lỗi bạn gặp khi deploy lên cloud (build fail, health check
timeout, sai REDIS_URL, app không đọc `$PORT`...): thông báo lỗi là gì, bạn
tìm ra nguyên nhân bằng cách nào, và sửa ra sao?

Tôi deploy lên **Railway** (project `day12-chat-2A202601650`, service `chat` +
Redis add-on). Lần deploy đầu **thất bại ở bước health check dù build thành
công** — đúng cái tình huống khó chịu nhất, vì log build toàn màu xanh.

**Thông báo lỗi.** Trên màn hình deploy:

```
====================
Starting Healthcheck
====================
Path: /healthz
Retry window: 30s

Attempt #1 failed with service unavailable. Continuing to retry for 19s
Attempt #2 failed with service unavailable. Continuing to retry for 8s
Deploy failed
```

**Cách tìm nguyên nhân.** "Service unavailable" chỉ nói *không ai trả lời cổng
đó*, chứ không nói vì sao — nên tôi không đoán, tôi đi đọc log của container:

```bash
$ railway logs --service chat --deployment
Starting Container
Usage: uvicorn [OPTIONS] APP
Error: Invalid value for '--port': '$PORT' is not a valid integer.
Error: Invalid value for '--port': '$PORT' is not a valid integer.
Error: Invalid value for '--port': '$PORT' is not a valid integer.
```

Đọc được dòng này thì mọi thứ sáng ra ngay: uvicorn nhận `--port` với giá trị
là **chuỗi 5 ký tự `$PORT`**, không phải số. Container khởi động, crash, được
restart, crash lại — crash loop. Health check không bao giờ có ai trả lời, và
sau 30 giây Railway bỏ cuộc.

Nguyên nhân nằm ở `railway.toml` mà lab cho sẵn:

```toml
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

Railway thực thi `startCommand` **không qua shell**. Không có shell thì không
ai nội suy `$PORT`, nên nó được truyền nguyên văn như một argument. Điều đáng
chú ý: `CMD` trong Dockerfile của tôi viết đúng
(`sh -c "exec uvicorn ... --port ${PORT:-8000}"`), nhưng `startCommand` trong
`railway.toml` **ghi đè** `CMD`, nên phần viết đúng đó không bao giờ được chạy.
Tôi mất mấy phút mới nhận ra chỗ này, vì bản chạy `docker compose` ở máy — nơi
`CMD` được dùng — hoạt động hoàn hảo.

**Cách sửa.** Tự bọc shell trong `startCommand`:

```toml
startCommand = "sh -c 'exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}'"
healthcheckTimeout = 120
```

Deploy lại → `Deploy complete`, rồi `railway domain --port 8000` cấp URL công
khai. Kiểm tra thật qua Internet:

```
$ curl -i https://chat-production-620e.up.railway.app/healthz
HTTP/2 200
{"status":"ok","service":"day12-chat-service","version":"1.0.0"}

$ curl -i https://chat-production-620e.up.railway.app/readyz
HTTP/2 200
{"status":"ready","redis":true}
```

`/readyz` trả `redis: true` là bằng chứng service nối được Redis add-on qua
private network `redis.railway.internal` — tôi set `REDIS_URL` bằng service
reference `${{Redis.REDIS_URL}}` nên giá trị thật không nằm ở đâu trong repo.

**Ba điều tôi học được từ lỗi này:**

1. **`sh -c` là bắt buộc nếu muốn nội suy biến môi trường trong lệnh khởi
   động.** Exec form (`["uvicorn", "--port", "$PORT"]`) hay `startCommand`
   không-qua-shell đều truyền `$PORT` nguyên văn. Đây là lý do tôi viết `CMD`
   trong Dockerfile ở dạng shell form ngay từ đầu — chỉ là tôi không biết
   `railway.toml` sẽ ghi đè nó.
2. **`exec` để giữ PID 1.** Nếu chỉ viết `sh -c 'uvicorn ...'` thì `sh` là PID
   1, và `sh` không chuyển SIGTERM xuống process con. Railway gửi SIGTERM mỗi
   lần deploy bản mới; không nhận được thì toàn bộ phần graceful shutdown ở CP4
   thành vô nghĩa và container luôn bị SIGKILL. Tôi kiểm tra lại bằng cách bấm
   thời gian `docker stop` ở máy: container thoát sau **549 ms**, exit code 0,
   và kịp ghi `{"event": "service_stopped", ...}`. Nếu SIGTERM không tới đúng
   process, lệnh đó sẽ treo hết 30 giây `stop_grace_period` rồi mới bị giết.
3. **Đọc log container, đừng đọc thông báo của orchestrator.**
   "Service unavailable" là *triệu chứng* mà health check nhìn thấy từ bên
   ngoài; nguyên nhân luôn nằm trong stdout của process. Toàn bộ chẩn đoán này
   gói lại thành đúng một lệnh `railway logs`, và nó chỉ hữu ích vì app ghi log
   ra stdout theo đúng cách CP1 yêu cầu.

Một lỗi thứ hai nhỏ hơn, cùng họ với nó: cổng `8000` ở máy tôi đang bị một
project khác chiếm, `docker compose up` báo
`Bind for 0.0.0.0:8000 failed: port is already allocated`. Tôi không tắt
project kia mà làm cổng host thành tham số: `"${CHAT_HOST_PORT:-8000}:8000"`,
rồi đặt `CHAT_HOST_PORT=8001` trong `.env`. Mặc định vẫn là `8000:8000` cho
người khác clone về. Cổng *bên trong* container không đổi, nên `REDIS_URL`,
healthcheck và nginx không phải sửa gì. Bài học chung của cả hai lỗi: **cổng là
thứ thuộc về môi trường, không thuộc về app** — đúng tinh thần 12-Factor, và
cũng là lý do trên cloud tôi không được phép cố định cổng nào cả.

Lỗi thứ ba, không liên quan tới code: khi thử phần điểm cộng nginx, Docker Hub
trả `429 Too Many Requests` cho `nginx:1.27-alpine` — rate limit của registry
với người dùng chưa đăng nhập. Tôi chuyển sang chứng minh tính stateless bằng
cách khác: `--scale chat=3` rồi gọi `/chat` lần lượt vào từng container với cùng
một `X-Client-Id`, và `turns_before` trả về `0 → 2 → 4 → 6 → 8 → 10` theo thứ
tự chat-1, chat-2, chat-3, chat-1, chat-2, chat-3. Ba process khác nhau, ba
vùng RAM khác nhau, nhưng cùng thấy một lịch sử hội thoại — vì lịch sử nằm
trong Redis chứ không nằm trong process. Trên Railway tôi thấy lại đúng điều
đó: gọi `/chat` hai lần với cùng `client_id` thì `turns_before` tăng từ 0 lên
2, dù giữa hai lần đó Railway hoàn toàn có thể đã chuyển tôi sang một instance
khác.

Lỗi thứ hai đáng ghi lại: khi thử phần điểm cộng nginx, Docker Hub trả
`429 Too Many Requests` cho `nginx:1.27-alpine`. Đây là rate limit của registry
với người dùng chưa đăng nhập, không phải lỗi cấu hình. Tôi chuyển sang chứng
minh tính stateless bằng cách khác: `--scale chat=3` rồi gọi `/chat` lần lượt
vào từng container với cùng một `X-Client-Id`, và `turns_before` trả về
`0 → 2 → 4 → 6 → 8 → 10` theo thứ tự chat-1, chat-2, chat-3, chat-1, chat-2,
chat-3. Ba process khác nhau, ba vùng RAM khác nhau, nhưng cùng thấy một lịch
sử hội thoại — vì lịch sử nằm trong Redis chứ không nằm trong process. Đó là
bằng chứng trực tiếp cho điều CP4 nói, và cũng cho thấy: trên cloud, nơi
platform tự scale và tự restart container bất cứ lúc nào, một `dict` trong RAM
sẽ hỏng theo cách rất khó tái hiện.
