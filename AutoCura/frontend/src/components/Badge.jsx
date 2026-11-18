import { statusTone } from "../utils/format";

export function Badge({ children }) {
  return <span className={`badge ${statusTone(children)}`}>{children}</span>;
}
