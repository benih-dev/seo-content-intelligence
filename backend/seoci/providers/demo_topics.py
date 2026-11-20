import re


def topic(keyword):
    if re.search(r"kebun|tanam|balkon|garden|plant|balcon", keyword, re.I):
        return "gardening"
    if re.search(r"dana|darurat|tabungan|emergency|savings|budget", keyword, re.I):
        return "savings"
    return "general"


def topic_sources(keyword):
    if topic(keyword) == "gardening":
        return [{"url": "https://extension.umn.edu/planting-and-growing-guides/container-gardening",
                 "title": "Container gardening — University of Minnesota Extension",
                 "snippet": "Container gardening requires attention to drainage, suitable growing media, light and watering. Demo summary: check original source context."},
                {"url": "https://www.rhs.org.uk/vegetables/growing-in-containers",
                 "title": "Vegetables in containers — Royal Horticultural Society",
                 "snippet": "Match vegetables to the available container space and growing conditions. Demo summary: verify crop-specific requirements before planting."}]
    if topic(keyword) == "savings":
        return [{"url": "https://www.consumerfinance.gov/an-essential-guide-to-building-an-emergency-fund/",
                 "title": "An essential guide to building an emergency fund — CFPB",
                 "snippet": "An emergency fund is a cash reserve set aside for unplanned expenses or financial emergencies. Demo summary: verify source and local applicability."},
                {"url": "https://www.consumerfinance.gov/consumer-tools/budgeting/",
                 "title": "Budgeting — Consumer Financial Protection Bureau",
                 "snippet": "A budget helps organize income, spending and savings decisions. Demo summary: not personalized financial advice."}]
    return []


def practical_notes(keyword, indo):
    kind = topic(keyword)
    if kind == "gardening":
        if indo:
            return [
                "Untuk kebun balkon, amati arah cahaya dan bagian yang terkena angin sebelum membeli tanaman. Periksa aturan bangunan, keamanan pagar, serta kemampuan area menahan pot dan media yang basah. Jangan menggantung wadah di luar pagar. Jika batas beban belum jelas, mintalah konfirmasi pengelola bangunan, bukan memperkirakannya sendiri.",
                "Pilih wadah berlubang drainase dan media tanam yang sesuai untuk pot. Tanah kebun yang padat tidak selalu cocok digunakan langsung dalam wadah. Sayuran daun, herba, dan tanaman berbuah memiliki kebutuhan cahaya serta ruang akar berbeda: cocokkan jenis tanaman dengan label budidaya dan kondisi balkon, bukan hanya foto hasil panen.",
                "Sebelum menyiram, periksa kelembapan media dan kondisi tanaman. Hindari jadwal kaku yang mengabaikan hujan, panas, ukuran pot, atau angin. Pastikan kelebihan air dapat keluar tanpa menetes ke balkon tetangga; bersihkan penampung air dan jangan membiarkan akar terus terendam. Gunakan pupuk sesuai label, bukan menambah dosis untuk mengejar pertumbuhan.",
                "Contoh khusus: balkon yang teduh tidak perlu dipaksa menanam tanaman buah yang membutuhkan cahaya kuat. Mulailah dengan tanaman yang rekomendasi cahayanya sesuai lokasi. Catat perubahan daun, kelembapan media, dan hambatan perawatan. Bila tanaman layu, periksa media serta akar sebelum menyimpulkan bahwa tanaman selalu kekurangan air.",
                "**Mengapa pot perlu drainase?** Lubang pembuangan membantu kelebihan air keluar; kebutuhan penyiraman tetap bergantung pada tanaman dan kondisi media. **Bolehkah langsung memakai pestisida?** Identifikasi masalah terlebih dahulu dan ikuti aturan serta label produk; jangan menggunakan campuran rumah tangga yang belum diketahui keamanannya untuk tanaman pangan.",
                "Langkah berikutnya adalah memilih tanaman yang sesuai cahaya, menyiapkan wadah yang aman, lalu membuat catatan perawatan. Panduan [University of Minnesota Extension](https://extension.umn.edu/planting-and-growing-guides/container-gardening) dan [RHS](https://www.rhs.org.uk/vegetables/growing-in-containers) menjadi titik awal pemeriksaan kebutuhan budidaya; sesuaikan dengan iklim dan varietas setempat."
            ]
        return [
            "For a balcony garden, observe light and wind before buying plants. Check building rules, railing safety and the permitted load for wet containers. Do not hang heavy containers outside railings. Ask the building manager about structural limits rather than estimating them yourself.",
            "Choose containers with drainage holes and growing media intended for pots. Dense garden soil may perform poorly in a container. Leafy greens, herbs and fruiting vegetables have different light and root-space requirements; match the crop's growing guidance to your actual location rather than to an attractive harvest photograph.",
            "Check the growing medium before watering. A rigid schedule cannot account for rain, heat, wind or container size. Allow excess water to escape without dripping onto neighboring balconies. Keep catch trays clean and avoid leaving roots submerged. Follow fertilizer labels rather than increasing the dose to force growth.",
            "For example, a shaded balcony need not be forced to support a sun-demanding fruiting crop. Begin with plants whose documented light requirements match the site. Record changes in leaves and media moisture. If a plant wilts, inspect drainage and root conditions before assuming that more water is always the answer.",
            "**Why does drainage matter?** It allows excess water to escape, although watering needs still depend on the crop and medium. **Should I apply a pesticide immediately?** Identify the problem first and follow local rules and product labels, especially for edible plants. Avoid untested household mixtures.",
            "Choose a suitable crop, prepare a safe container and keep care notes. Consult [University of Minnesota Extension](https://extension.umn.edu/planting-and-growing-guides/container-gardening) and the [RHS](https://www.rhs.org.uk/vegetables/growing-in-containers) for growing guidance, then adapt it to the local climate and variety."
        ]
    if kind == "savings":
        if indo:
            return [
                "Untuk dana darurat, pisahkan pengeluaran rutin yang dapat diperkirakan dari kejadian tidak terencana. Tagihan tahunan sebaiknya memiliki pos anggaran tersendiri; kehilangan penghasilan atau perbaikan mendesak memerlukan rencana cadangan. Catat kebutuhan pokok, tanggungan, dan kestabilan penghasilan tanpa mengikuti target nominal orang lain.",
                "Bandingkan tempat menyimpan dana berdasarkan akses, biaya, risiko kehilangan nilai, dan perlindungan simpanan yang berlaku di negara Anda. Jangan menganggap produk investasi yang harganya berfluktuasi setara dengan uang tunai yang dibutuhkan mendadak. Periksa syarat penarikan serta status lembaga melalui sumber regulator lokal.",
                "Tentukan kontribusi yang tidak mengorbankan kebutuhan pokok atau menimbulkan utang baru. Jika penghasilan tidak tetap, evaluasi saat pemasukan diterima. Otomatisasi dapat membantu bila saldo mencukupi, tetapi periksa potensi biaya atau gagal debit. Pisahkan catatan dana darurat dari uang untuk tujuan belanja lainnya.",
                "Ilustrasi: seorang pekerja lepas menerima pemasukan tidak merata. Ia membuat daftar pengeluaran esensial, menentukan cadangan awal yang realistis, dan meninjau kontribusi setelah menerima pembayaran. Ketika biaya perbaikan mendesak terjadi, ia mencatat alasan penggunaan dana lalu menyusun rencana pengisian kembali. Tidak ada nominal atau imbal hasil yang dijanjikan.",
                "**Apakah target semua orang sama?** Tidak. Kebutuhan bergantung pada kewajiban, kestabilan pemasukan, dan akses dukungan. **Bolehkah dana dipakai?** Tentukan terlebih dahulu kriteria keadaan darurat dan rencana mengisinya kembali. Untuk keputusan yang melibatkan utang besar, pajak, atau produk keuangan kompleks, konsultasikan kepada profesional yang kompeten.",
                "Buat daftar kebutuhan esensial dan pilih tempat penyimpanan setelah memeriksa syarat lokal. [Panduan CFPB](https://www.consumerfinance.gov/an-essential-guide-to-building-an-emergency-fund/) memberi kerangka umum dana darurat, tetapi berasal dari konteks Amerika Serikat. Jangan menganggap ketentuan perlindungan atau produk di sana berlaku di Indonesia. Artikel ini merupakan edukasi umum, bukan nasihat keuangan personal."
            ]
        return [
            "For an emergency fund, separate predictable bills from genuinely unplanned expenses. Annual bills can have their own savings category; income loss or an urgent repair calls for a contingency plan. Consider essential expenses, dependents and income stability rather than copying another household's target.",
            "Compare storage options by access, fees, risk to principal and locally applicable deposit protection. A volatile investment is not interchangeable with cash needed unexpectedly. Check withdrawal conditions and the institution's status using your local regulator's information.",
            "Choose contributions that do not displace essentials or create new borrowing. If income varies, review contributions when payments arrive. Automation may help when the balance supports it, but check potential overdraft or failed-transfer fees. Keep emergency savings separate in your records from planned spending.",
            "Consider a hypothetical freelancer with irregular payments. They list essential expenses, choose a manageable initial reserve and revisit contributions after invoices are paid. When an urgent repair occurs, they record why it qualifies and make a replenishment plan. This example promises no particular balance or investment return.",
            "**Does everyone need the same target?** No. Obligations, income stability and support networks differ. **Can the fund be used?** Define emergency criteria in advance and plan how to replenish it. Seek qualified advice for decisions involving substantial debt, tax or complex financial products.",
            "List essential needs and examine local account terms before choosing storage. The [CFPB emergency fund guide](https://www.consumerfinance.gov/an-essential-guide-to-building-an-emergency-fund/) offers a general framework in a US context; do not assume its regulatory context applies elsewhere. This is general education, not personalized financial advice."
        ]
    return []
