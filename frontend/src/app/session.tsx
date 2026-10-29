// 상담원·부서·기준 시각 (SCR-00-02~04, D23·D33). 브라우저 저장소에 기억하고(principles §4), 요청 머리는 api.ts가 싣는다.
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import {
  agentDept, agentId, asOfMode, saveAgentDept, saveAgentId, saveAsOfMode, SNAPSHOT, type AsOfMode,
} from "../api";

export interface Session {
  agent: string;
  dept: string;
  mode: AsOfMode;
  /** 조회에 싣는 기준 시각. 실제 시각이면 null(서버가 지금으로 계산) */
  asOf: string | null;
  setAgent: (agent: string) => void;
  setDept: (dept: string) => void;
  setMode: (mode: AsOfMode) => void;
}

const Ctx = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [agent, setAgentState] = useState(agentId());
  const [dept, setDeptState] = useState(agentDept());
  const [mode, setModeState] = useState<AsOfMode>(asOfMode());

  const setAgent = useCallback((next: string) => { saveAgentId(next); setAgentState(next); }, []);
  const setDept = useCallback((next: string) => { saveAgentDept(next); setDeptState(next); }, []);
  const setMode = useCallback((next: AsOfMode) => { saveAsOfMode(next); setModeState(next); }, []);

  const value = useMemo<Session>(() => ({
    agent, dept, mode, asOf: mode === "snapshot" ? SNAPSHOT : null, setAgent, setDept, setMode,
  }), [agent, dept, mode, setAgent, setDept, setMode]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  const s = useContext(Ctx);
  if (!s) throw new Error("SessionProvider 밖에서 useSession을 불렀다");
  return s;
}
