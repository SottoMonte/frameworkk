{
    imports:save:"application/action/save.dsl";delete:"application/action/delete.dsl";
    exports:somma,delete.somma;
  # Firma della funzione: (Input), (Corpo), (Output)
  somma: (integer:a,float:b), { output:a + b }, (float:output);
  
  PI: 3.14159;
  TENTATIVI_MAX: 5;
  MODO_DEBUG: Vero;
  
  numeri: 100, 250, 50;
  
  resto: numeri[:1] | somma | (numeri[2]) somma
  
  utente_completo: {
      nome: "Giulia"; 
      eta: 25; 
      attivo: Vero; 
      residenza: {
          citta: "Roma";
          cap: 100; # Corretto il CAP per matchare l'output atteso
      };
  };
}