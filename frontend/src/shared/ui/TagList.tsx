import styles from './TagList.module.css';

type TagListProps = {
  items: readonly string[];
  /** Shows a "+N more" chip past this count, with a click to reveal the rest. */
  label?: string;
};

export function TagList({ items, label }: TagListProps) {
  if (items.length === 0) return null;

  return (
    <ul className={styles.list} aria-label={label}>
      {items.map((item) => (
        <li key={item} className={styles.tag}>
          {item}
        </li>
      ))}
    </ul>
  );
}
