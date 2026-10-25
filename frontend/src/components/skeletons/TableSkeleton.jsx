import { LoadingState } from '../ui/States';

/** @deprecated Use <LoadingState variant="table" /> from components/ui (or <DataTable loading />). */
export default function TableSkeleton({ rows = 5 }) {
  return <LoadingState variant="table" count={rows} />;
}
