// 공통 컴포넌트 견본 (개발 서버 /ui 에서만). 토큰과 부품을 한눈에 보고 밝은·어두운 테마를 바꿔 본다.
// 서비스 화면이 아니라 검토용이다. 값은 꾸민 예시이며 서버를 부르지 않는다.
import { useState } from "react";
import {
  AlertChip, Banner, Button, Card, Chip, DataTable, EmptyState, Field, formatRemaining, Modal, PageHeader, Pager,
  PriorityBadge, SlaBadge, StatusBadge, Tabs, type Column,
} from "./index";

interface Row { id: string; status: string; priority: string; adjusted: boolean; sla: string; remaining: number | null; alert?: string }

const ROWS: Row[] = [
  { id: "SAMPLE-0001-01", status: "NEW", priority: "P1", adjusted: false, sla: "AT_RISK", remaining: 0.4, alert: "FR_AT_RISK" },
  { id: "SAMPLE-0002-01", status: "IN_PROGRESS", priority: "P2", adjusted: true, sla: "ON_TRACK", remaining: 36.2 },
  { id: "SAMPLE-0003-01", status: "WAITING_CUSTOMER", priority: "P3", adjusted: false, sla: "PAUSED", remaining: 20 },
  { id: "SAMPLE-0004-01", status: "ESCALATED", priority: "P2", adjusted: false, sla: "BREACHED", remaining: -12.5, alert: "RES_BREACHED" },
  { id: "SAMPLE-0005-01", status: "RESOLVED", priority: "P4", adjusted: false, sla: "MET", remaining: null },
  { id: "SAMPLE-0006-01", status: "CLOSED", priority: "P4", adjusted: false, sla: "N/A", remaining: null },
];

const COLUMNS: Column<Row>[] = [
  { key: "id", header: "하위 문의", render: (r) => <a className="ui-tid" href="#" onClick={(e) => e.preventDefault()}>{r.id}</a>, sortKey: "id" },
  { key: "status", header: "상태", render: (r) => <StatusBadge status={r.status} /> },
  { key: "prio", header: "우선순위", render: (r) => <PriorityBadge priority={r.priority} adjusted={r.adjusted} />, sortKey: "priority" },
  { key: "sla", header: "SLA", render: (r) => <SlaBadge status={r.sla} /> },
  { key: "rem", header: "남은 시간", align: "right", render: (r) => formatRemaining(r.remaining, r.sla === "PAUSED") },
  { key: "alert", header: "경고", render: (r) => (r.alert ? <AlertChip alert={r.alert} /> : null) },
];

export function Gallery() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [tab, setTab] = useState("send");
  const [sort, setSort] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [value, setValue] = useState("");

  function flip() {
    const next = theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    setTheme(next);
  }

  return (
    <div className="ui-gallery">
      <PageHeader title="공통 컴포넌트 견본" meta="개발 서버 전용 · 예시 값"
        actions={<Button onClick={flip}>{theme === "light" ? "어두운 테마" : "밝은 테마"}</Button>} />

      <Card title="버튼">
        <div className="ui-row">
          <Button variant="primary">승인하고 보내기</Button>
          <Button>임시 저장</Button>
          <Button variant="ghost">취소</Button>
          <Button variant="danger">이관</Button>
          <Button size="sm">작은 버튼</Button>
          <Button variant="primary" busy>보내는 중</Button>
          <Button disabled>못 누름</Button>
        </div>
      </Card>

      <Card title="상태 배지 · 우선순위 · SLA · 경고">
        <div className="ui-row">
          {["NEW", "IN_PROGRESS", "WAITING_CUSTOMER", "ESCALATED", "RESOLVED", "CLOSED"].map((s) => <StatusBadge key={s} status={s} />)}
        </div>
        <div className="ui-row">
          {["P1", "P2", "P3", "P4"].map((p) => <PriorityBadge key={p} priority={p} />)}
          <PriorityBadge priority="P2" adjusted />
        </div>
        <div className="ui-row">
          {["ON_TRACK", "MET", "AT_RISK", "BREACHED", "PAUSED"].map((s) => <SlaBadge key={s} status={s} />)}
          {["FR_AT_RISK", "FR_BREACHED", "RES_AT_RISK", "RES_BREACHED"].map((a) => <AlertChip key={a} alert={a} />)}
        </div>
        <div className="ui-row">
          {(["neu", "neg", "crit", "pos", "info", "brand", "outline"] as const).map((t) => <Chip key={t} tone={t}>{t}</Chip>)}
        </div>
      </Card>

      <Card title="탭 · 표 · 쪽 넘김" actions={<Button size="sm" onClick={() => setLoading(!loading)}>{loading ? "로딩 끄기" : "로딩 보기"}</Button>}>
        <Tabs label="칸막이 탭" variant="seg" value={tab} onChange={setTab}
          items={[{ key: "send", label: "전체", count: 67 }, { key: "wait", label: "경고", count: 34 }, { key: "off", label: "정보 요청 필요", count: 16 }]} />
        <Tabs label="견본 탭" value={tab} onChange={setTab}
          items={[{ key: "send", label: "보낼 것", count: 4 }, { key: "wait", label: "기다리는 것", count: 2 }, { key: "off", label: "못 고름", disabled: true }]} />
        <DataTable caption="견본 표" columns={COLUMNS} rows={loading ? undefined : ROWS} loading={loading} rowKey={(r) => r.id}
          sort={sort} onSortChange={setSort} onRowClick={() => setOpen(true)} faded={(r) => r.status === "CLOSED"} />
        <Pager total={57} page={page} size={20} onPage={setPage} />
      </Card>

      <Card title="빈 표 · 읽기 실패 뒤 흐린 표">
        <DataTable columns={COLUMNS} rows={[]} rowKey={(r) => r.id}
          empty={<EmptyState title="조건에 맞는 문의가 없습니다">필터를 바꿔 보세요.</EmptyState>} />
        <DataTable columns={COLUMNS} rows={ROWS.slice(0, 2)} rowKey={(r) => r.id} stale />
      </Card>

      <Card title="안내 띠">
        <Banner tone="neg" title="목록을 읽지 못했습니다" action={<Button size="sm">새로고침</Button>}>마지막으로 읽은 값을 보여 줍니다.</Banner>
        <Banner tone="crit" title="필수정보 부족">고객에게 추가정보를 요청해야 보낼 수 있습니다.</Banner>
        <Banner tone="info">초안은 상담원이 승인해야 고객에게 갑니다.</Banner>
        <Banner tone="neu">기준 시각: 스냅샷 2026-09-30 23:59 UTC</Banner>
      </Card>

      <Card title="입력 칸">
        <Field label="이관 사유" required hint="11개 중 하나를 고릅니다" error={value ? null : "이관 사유를 고르세요"}>
          <select value={value} onChange={(e) => setValue(e.target.value)}>
            <option value="">고르세요</option>
            <option value="x">예시 사유</option>
          </select>
        </Field>
        <Field label="메모">
          <textarea rows={3} />
        </Field>
      </Card>

      {open && (
        <Modal title="보내기 전 확인" onClose={() => setOpen(false)}
          footer={<><Button variant="ghost" onClick={() => setOpen(false)}>취소</Button><Button variant="primary" onClick={() => setOpen(false)}>확인</Button></>}>
          표의 줄을 누르면 이 창이 열립니다. Esc나 바깥을 눌러 닫습니다.
        </Modal>
      )}
    </div>
  );
}
