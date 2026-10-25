import { LoadingState } from '../ui/States';

/** @deprecated Use <LoadingState variant="list" /> from components/ui. */
export default function ListSkeleton({ rows = 5 }) {
  return <LoadingState variant="list" count={rows} />;
}
