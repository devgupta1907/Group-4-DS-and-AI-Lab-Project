import styles from './SectionHeader.module.css';

type Props = { number: string; title: string; description: string };

export function SectionHeader({ number, title, description }: Props) {
  return (
    <header className={styles.header}>
      <span>{number}</span>
      <div><h2>{title}</h2><p>{description}</p></div>
    </header>
  );
}
