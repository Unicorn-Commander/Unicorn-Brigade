import { LoadingState } from '../ui/States';

/** @deprecated Use <LoadingState variant="cards" /> from components/ui. Kept as a thin alias so existing pages migrate for free. */
export default function CardSkeleton({ count = 1 }) {
  return <LoadingState variant="cards" count={count} />;
}
