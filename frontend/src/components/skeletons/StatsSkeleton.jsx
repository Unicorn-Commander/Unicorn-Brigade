import { LoadingState } from '../ui/States';

/** @deprecated Use <LoadingState variant="stats" /> from components/ui. */
export default function StatsSkeleton({ count = 4 }) {
  return <LoadingState variant="stats" count={count} />;
}
