import pandas as pd
import os

def merge_and_validate_rows(input_file, category_dir, output_file):
    # Caricare il file principale
    data = pd.read_csv(input_file)

    # Preparare un nuovo DataFrame per il risultato
    merged_data = []

    i = 0
    while i < len(data):
        row = data.iloc[i]

        # Unire l'item corrente con l'item successivo
        if i + 1 < len(data):
            merged_item_2 = (
                str(data.iloc[i]['item']) +
                str(data.iloc[i + 1]['item'])
            ).replace("'", "").replace(" ", "")

            # Controllare il file della categoria corrispondente
            category_file = os.path.join(category_dir, f"{row['category']}.csv")
            if os.path.exists(category_file):
                try:
                    # Caricare solo la seconda colonna
                    category_data = pd.read_csv(category_file, header=None, usecols=[1])
                except Exception as e:
                    print(f"Errore durante il caricamento di {category_file}: {e}")
                    continue

                # Controllare se l'item unito esiste nella seconda colonna
                if merged_item_2 in category_data.iloc[:, 0].values:
                    # Sostituire i due item con l'unione
                    row['item'] = merged_item_2
                    merged_data.append(row)
                    i += 2  # Saltare la riga successiva
                    continue

        # Unire l'item corrente con i due successivi
        if i + 2 < len(data):
            merged_item_3 = (
                str(data.iloc[i]['item']) +
                str(data.iloc[i + 1]['item']) +
                str(data.iloc[i + 2]['item'])
            ).replace("'", "").replace(" ", "")

            # Controllare il file della categoria corrispondente
            if os.path.exists(category_file):
                try:
                    # Caricare solo la seconda colonna
                    category_data = pd.read_csv(category_file, header=None, usecols=[1])
                except Exception as e:
                    print(f"Errore durante il caricamento di {category_file}: {e}")
                    continue

                # Controllare se l'item unito esiste nella seconda colonna
                if merged_item_3 in category_data.iloc[:, 0].values:
                    # Sostituire i tre item con l'unione
                    row['item'] = merged_item_3
                    merged_data.append(row)
                    i += 3  # Saltare le due righe successive
                    continue

        # Aggiungere la riga corrente senza modifiche
        merged_data.append(row)
        i += 1

    # Creare un nuovo DataFrame con i dati uniti
    merged_df = pd.DataFrame(merged_data)

    # Salvare il risultato in un file CSV
    merged_df.to_csv(output_file, index=False)
    print(f"File salvato con successo in: {output_file}")

# Percorsi

def main():
    input_file = 'fluency_data/snafu.csv'
    category_dir = 'schemes/'  # Directory con i file categoria.csv
    output_file = 'fluency_data/filtered_snafu.csv'

    merge_and_validate_rows(input_file, category_dir, output_file)


if __name__ == "__main__":
    main()


